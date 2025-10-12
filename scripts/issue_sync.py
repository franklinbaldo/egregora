"""Synchronize Markdown issues in ``dev/issues`` with GitHub Issues.

This script keeps the Markdown files under ``dev/issues`` in sync with
GitHub issues in a bidirectional manner.  It is intended to be executed by
automation (e.g. GitHub Actions) but can also be invoked manually.

Synchronization strategy
------------------------

* Each Markdown file may contain a metadata block at the very top in an HTML
  comment.  The script maintains the following keys:

  - ``github_issue`` – GitHub issue number associated with the file.
  - ``github_state`` – ``open`` or ``closed``.
  - ``github_state_synced`` – last GitHub state seen during synchronization.
  - ``last_synced`` – timestamp of the last synchronization (ISO 8601).
  - ``sync_hash`` – SHA-256 hash of the Markdown body at last synchronization.

* The Markdown content (everything after the metadata block) is mirrored to the
  GitHub issue body verbatim.  The GitHub issue title is derived from the first
  Markdown heading.

* When both the local file and the GitHub issue have diverged since the last
  sync, the newer change wins based on the file's last modification timestamp
  versus the GitHub issue body's last edit timestamp reported by the timeline
  API.  This avoids unrelated activity (e.g. comments) from overwriting fresher
  local edits.

* New Markdown files that do not reference a GitHub issue result in new issues
  being created.  Conversely, GitHub issues without a local file generate new
  Markdown files under ``dev/issues`` prefixed with ``github-``.

The GitHub repository (``owner/name``) and token are automatically detected
from the ``GITHUB_REPOSITORY`` and ``GITHUB_TOKEN`` environment variables, but
they can be overridden via command-line options.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib import error, request

ISSUES_DIR_DEFAULT = Path("dev/issues")
METADATA_ORDER = (
    "github_issue",
    "github_state",
    "github_state_synced",
    "last_synced",
    "sync_hash",
)

LOGGER = logging.getLogger("egregora.issue_sync")


def _log_info(message: str) -> None:
    LOGGER.info(message)


def _log_warning(message: str) -> None:
    LOGGER.warning(message)


def _now_utc() -> datetime:
    return datetime.now(tz=UTC)


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_iso8601(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def slugify(text: str, *, fallback: str = "issue") -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\-\s]+", "", text)
    text = re.sub(r"\s+", "-", text)
    text = text.strip("-")
    if ".." in text:
        text = text.replace("..", "-")
    return text or fallback


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_state(value: str | None) -> str:
    return "closed" if str(value or "open").lower() == "closed" else "open"


def read_metadata(text: str) -> tuple[dict[str, str], str]:
    text = text.lstrip("\ufeff")
    if not text.startswith("<!--"):
        return {}, text

    end_idx = text.find("-->")
    if end_idx == -1:
        return {}, text

    block = text[4:end_idx].strip()
    metadata: dict[str, str] = {}
    for line in block.splitlines():
        clean_line = line.strip()
        if not clean_line or clean_line.startswith("#"):
            continue
        if ":" not in clean_line:
            continue
        key, value = clean_line.split(":", 1)
        metadata[key.strip()] = value.strip()

    remainder = text[end_idx + 3 :]
    if remainder.startswith("\n"):
        remainder = remainder[1:]
    return metadata, remainder


def format_metadata(metadata: dict[str, str]) -> str:
    lines = ["<!--"]
    for key in METADATA_ORDER:
        value = metadata.get(key)
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    for key in sorted(metadata):
        if key in METADATA_ORDER:
            continue
        lines.append(f"{key}: {metadata[key]}")
    lines.append("-->")
    return "\n".join(lines)


def extract_local_identifier(header_line: str) -> str | None:
    match = re.match(r"^#\s*(\d+)", header_line)
    if match:
        return match.group(1).strip()
    return None


def extract_title(filename: str) -> str:
    # Extract title from filename (e.g., "001-My-Issue-Title.md" -> "My-Issue-Title")
    match = re.match(r"^\d+-(.*)\.md$", filename)
    if match:
        return match.group(1).replace("-", " ").strip()
    return "Untitled issue"


def ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def get_git_commit_time(path: Path) -> datetime | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0:
        return None

    timestamp = result.stdout.strip()
    if not timestamp:
        return None

    try:
        return datetime.fromisoformat(timestamp).astimezone(UTC)
    except ValueError:
        return None


def get_file_modification_time(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


@dataclass(slots=True)
class LocalIssue:
    path: Path
    metadata: dict[str, str]
    content: str
    content_hash: str
    header_line: str
    title: str  # This is the title from the filename
    full_title: str  # This is the full title from the GitHub issue
    desired_state: str
    synced_state: str
    issue_number: int | None
    local_identifier: str | None
    last_synced: datetime | None
    sync_hash: str | None
    commit_time: datetime | None
    modified_time: datetime | None

    @property
    def body_for_github(self) -> str:
        return self.content.rstrip("\n")

    @property
    def stored_state(self) -> str:
        return normalize_state(self.metadata.get("github_state"))


def load_local_issues(directory: Path) -> list[LocalIssue]:
    issues: list[LocalIssue] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        metadata, body = read_metadata(text)
        body = ensure_trailing_newline(body)
        lines = body.splitlines()
        header_line = ""
        for line in lines:
            if line.strip():
                header_line = line
                break
        if not header_line:
            header_line = "# Untitled issue"
        title = extract_title(path.name)
        identifier = extract_local_identifier(header_line)
        desired_state = normalize_state(metadata.get("github_state"))
        synced_state = normalize_state(
            metadata.get("github_state_synced") or metadata.get("github_state")
        )
        issue_number = None
        raw_number = metadata.get("github_issue")
        if raw_number:
            try:
                issue_number = int(raw_number)
            except ValueError:
                issue_number = None
        last_synced = parse_iso8601(metadata.get("last_synced"))
        sync_hash = metadata.get("sync_hash")
        commit_time = get_git_commit_time(path)
        modified_time = get_file_modification_time(path)
        issues.append(
            LocalIssue(
                path=path,
                metadata=metadata,
                content=body,
                content_hash=compute_hash(body),
                header_line=header_line,
                title=title,
                desired_state=desired_state,
                synced_state=synced_state,
                issue_number=issue_number,
                local_identifier=identifier,
                last_synced=last_synced,
                sync_hash=sync_hash,
                commit_time=commit_time,
                modified_time=modified_time,
            )
        )
    return issues


def github_request(
    url: str,
    *,
    token: str,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[dict, dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "egregora-issue-sync",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data: bytes | None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        data = None

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}, dict(resp.headers.items())
    except error.HTTPError as exc:  # pragma: no cover - informative message
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"GitHub API request failed: {exc.code} {exc.reason}\n{details}"
        ) from exc


def github_paginated(
    url: str,
    *,
    token: str,
) -> Iterable[dict]:
    next_url: str | None = url
    while next_url:
        data, headers = github_request(next_url, token=token)
        if isinstance(data, list):
            yield from data
        else:
            yield data
            return
        link = headers.get("Link")
        next_url = None
        if link:
            for part in link.split(","):
                section = part.strip()
                if not section:
                    continue
                if '; rel="next"' in section:
                    url_part = section.split(";", 1)[0].strip()
                    if url_part.startswith("<") and url_part.endswith(">"):
                        next_url = url_part[1:-1]
                    break


def fetch_remote_issues(repo: str, token: str) -> dict[int, dict]:
    url = (
        f"https://api.github.com/repos/{repo}/issues"
        f"?state=all&per_page=100&direction=asc&sort=created"
    )
    issues: dict[int, dict] = {}
    for item in github_paginated(url, token=token):
        if not isinstance(item, dict):
            continue
        if "pull_request" in item:
            continue
        issues[int(item["number"])] = item
    return issues


def parse_remote_content(
    remote: dict,
    *,
    local_identifier: str | None = None,
) -> str:
    body = (remote.get("body") or "").replace("\r\n", "\n")
    if body.strip().startswith("#"):
        content = body
    else:
        local_identifier or f"{remote['number']:03d}"
        header = f"# {remote['title']}"
        github_url = f"GitHub Issue: [#{remote['number']}](https://github.com/franklinbaldo/egregora/issues/{remote['number']})"
        content = f"{header}\n\n{github_url}"
        if body.strip():
            content += "\n\n" + body.strip("\n")
    return ensure_trailing_newline(content)


def write_issue_file(issue: LocalIssue) -> None:
    metadata = issue.metadata.copy()
    metadata["github_state"] = issue.desired_state
    metadata["github_state_synced"] = issue.synced_state
    if issue.issue_number is not None:
        metadata["github_issue"] = str(issue.issue_number)
    if issue.last_synced is not None:
        metadata["last_synced"] = format_iso8601(issue.last_synced) or ""
    if issue.sync_hash is not None:
        metadata["sync_hash"] = issue.sync_hash

    metadata_block = format_metadata(metadata)
    content = metadata_block + "\n\n" + issue.content
    issue.path.write_text(content, encoding="utf-8")
    issue.metadata = metadata
    issue.modified_time = get_file_modification_time(issue.path)


def ensure_unique_path(base_dir: Path, filename: str) -> Path:
    safe_name = Path(filename).name
    if safe_name != filename:
        raise ValueError(f"Unsafe filename with path components: {filename}")

    base_dir_resolved = base_dir.resolve()
    path = base_dir / safe_name
    if not path.resolve().is_relative_to(base_dir_resolved):
        raise ValueError(f"Resolved path escapes base directory: {path}")
    if not path.exists():
        return path

    stem, suffix = os.path.splitext(safe_name)
    counter = 2
    while True:
        candidate = base_dir / f"{stem}-{counter}{suffix}"
        if not candidate.resolve().is_relative_to(base_dir_resolved):
            raise ValueError(f"Resolved path escapes base directory: {candidate}")
        if not candidate.exists():
            return candidate
        counter += 1


def create_local_issue_from_remote(
    directory: Path,
    remote: dict,
    *,
    token: str,
) -> LocalIssue:
    slug = slugify(remote.get("title", "issue"))
    filename = f"{int(remote['number']):03d}-{slug}.md"
    try:
        path = ensure_unique_path(directory, filename)
    except ValueError as exc:
        _log_warning(
            f"Unsafe path '{filename}' for GitHub issue #{remote['number']}: {exc}."
            " Using sanitized fallback filename."
        )
        fallback_filename = f"github-{int(remote['number']):05d}.md"
        path = ensure_unique_path(directory, fallback_filename)
    content = parse_remote_content(remote)
    content = f"# {int(remote['number'])}\n\n" + content
    remote_body_updated = get_remote_body_update_time(remote, token=token)

    remote_state = normalize_state(remote.get("state"))

    issue = LocalIssue(
        path=path,
        metadata={"github_issue": str(remote["number"]), "github_state": remote["state"]},
        content=content,
        content_hash=compute_hash(content),
        header_line=content.splitlines()[0],
        title=extract_title(content.splitlines()[0]),
        desired_state=remote_state,
        synced_state=remote_state,
        issue_number=int(remote["number"]),
        local_identifier=extract_local_identifier(content.splitlines()[0]),
        last_synced=remote_body_updated,
        sync_hash=compute_hash(content),
        commit_time=None,
        modified_time=None,
    )
    write_issue_file(issue)
    _log_info(f"📝 Created local issue for GitHub #{remote['number']} -> {path}")
    return issue


def get_remote_body_update_time(remote: dict, *, token: str) -> datetime | None:
    timeline_url = remote.get("timeline_url")
    fallback = parse_iso8601(remote.get("updated_at") or remote.get("created_at"))
    if not timeline_url:
        return fallback

    latest: datetime | None = None
    query_sep = "&" if "?" in timeline_url else "?"
    timeline_request_url = f"{timeline_url}{query_sep}per_page=100"

    try:
        for event in github_paginated(timeline_request_url, token=token):
            if not isinstance(event, dict):
                continue
            if event.get("event") != "edited":
                continue
            changes = event.get("changes")
            if not isinstance(changes, dict) or "body" not in changes:
                continue
            edited_at = parse_iso8601(event.get("created_at"))
            if edited_at and (latest is None or edited_at > latest):
                latest = edited_at
    except RuntimeError as exc:  # pragma: no cover - network failure fallback
        _log_warning(f"Unable to fetch issue timeline for body edit timestamp: {exc}")
        return fallback

    return latest or fallback


def update_remote_issue(
    repo: str,
    token: str,
    issue_number: int,
    *,
    title: str,
    body: str,
    state: str | None = None,
) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    payload = {"title": title, "body": body}
    if state is not None:
        normalized = normalize_state(state)
        payload["state"] = normalized
    data, _ = github_request(url, token=token, method="PATCH", payload=payload)
    return data


def create_remote_issue(
    repo: str,
    token: str,
    *,
    title: str,
    body: str,
) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {"title": title, "body": body}
    data, _ = github_request(url, token=token, method="POST", payload=payload)
    return data


def sync_existing_issue(
    repo: str,
    token: str,
    local: LocalIssue,
    remote: dict,
) -> None:
    remote_state = normalize_state(remote.get("state"))
    remote_content = parse_remote_content(remote, local_identifier=local.local_identifier)
    remote_hash = compute_hash(remote_content)

    stored_hash = local.sync_hash
    local_changed = stored_hash is None or local.content_hash != stored_hash
    remote_body_changed = stored_hash is None or remote_hash != stored_hash

    remote_updated_time = parse_iso8601(remote.get("updated_at"))
    local_state_changed = local.desired_state != local.synced_state
    remote_state_changed = remote_state != local.synced_state and (
        remote_updated_time is None
        or local.last_synced is None
        or remote_updated_time > local.last_synced
    )
    remote_changed = remote_body_changed or remote_state_changed

    local_time = get_file_modification_time(local.path) or local.modified_time or local.commit_time
    if local_time:
        local.modified_time = local_time

    remote_body_updated: datetime | None = None

    def ensure_remote_body_time() -> datetime | None:
        nonlocal remote_body_updated
        if remote_body_updated is None:
            remote_body_updated = get_remote_body_update_time(remote, token=token)
        return remote_body_updated

    chosen_source: str
    if remote_changed and not local_changed:
        chosen_source = "remote"
    elif local_changed and not remote_changed:
        chosen_source = "local"
    elif remote_changed and local_changed:
        remote_time = ensure_remote_body_time() if remote_body_changed else None
        if remote_time and local_time:
            chosen_source = "remote" if remote_time > local_time else "local"
        elif remote_time:
            chosen_source = "remote"
        elif local_time:
            chosen_source = "local"
        else:
            chosen_source = "local"
    else:
        chosen_source = "none"

    if chosen_source == "remote":
        local.content = remote_content
        local.content_hash = remote_hash
        local.desired_state = remote_state
        local.synced_state = remote_state
        local.last_synced = ensure_remote_body_time() or _now_utc()
        local.sync_hash = remote_hash
        write_issue_file(local)
        _log_info(
            f"⬇️  Updated local file from GitHub issue #{local.issue_number} ({local.path.name})"
        )
        return

    if chosen_source == "local":
        state_to_send: str | None
        if local_state_changed or not remote_state_changed:
            state_to_send = local.desired_state
        else:
            state_to_send = None
        response = update_remote_issue(
            repo,
            token,
            local.issue_number or int(remote["number"]),
            title=local.header_line.lstrip("#").strip() or local.title,
            body=local.body_for_github,
            state=state_to_send,
        )
        remote_updated = parse_iso8601(response.get("updated_at")) or _now_utc()
        response_state = normalize_state(response.get("state"))
        local.last_synced = remote_updated
        local.desired_state = response_state
        local.synced_state = response_state
        local.sync_hash = compute_hash(local.content)
        write_issue_file(local)
        _log_info(
            f"⬆️  Updated GitHub issue #{local.issue_number} from local file ({local.path.name})"
        )
        return

    if chosen_source == "none":
        # Ensure metadata is up-to-date even when no content changed.
        local.desired_state = remote_state
        local.synced_state = remote_state
        if remote_changed:
            local.last_synced = ensure_remote_body_time() or local.last_synced
        local.sync_hash = remote_hash
        write_issue_file(local)


def sync_local_without_remote(
    repo: str,
    token: str,
    local: LocalIssue,
) -> None:
    response = create_remote_issue(
        repo,
        token,
        title=local.header_line.lstrip("#").strip() or local.title,
        body=local.body_for_github,
    )
    issue_number = int(response["number"])
    remote_state = normalize_state(response.get("state"))
    remote_updated = parse_iso8601(response.get("updated_at")) or _now_utc()
    local.issue_number = issue_number
    local.desired_state = remote_state
    local.synced_state = remote_state
    local.last_synced = remote_updated
    local.sync_hash = compute_hash(local.content)
    write_issue_file(local)
    _log_info(f"🚀 Created GitHub issue #{issue_number} from {local.path.name}")

    if local.stored_state == "closed" and remote_state != "closed":
        response = update_remote_issue(
            repo,
            token,
            issue_number,
            title=local.header_line.lstrip("#").strip() or local.title,
            body=local.body_for_github,
            state=local.stored_state,
        )
        updated_state = normalize_state(response.get("state", local.stored_state))
        local.desired_state = updated_state
        local.synced_state = updated_state
        local.last_synced = parse_iso8601(response.get("updated_at")) or remote_updated
        local.sync_hash = compute_hash(local.content)
        write_issue_file(local)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=getattr(
            logging,
            os.environ.get("ISSUE_SYNC_LOG_LEVEL", "INFO").upper(),
            logging.INFO,
        ),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="GitHub repository in the form 'owner/name' (defaults to GITHUB_REPOSITORY).",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token (defaults to GITHUB_TOKEN).",
    )
    parser.add_argument(
        "--issues-dir",
        default=str(ISSUES_DIR_DEFAULT),
        help="Directory containing Markdown issues.",
    )
    args = parser.parse_args(argv)

    if not args.repo:
        parser.error("GitHub repository not provided. Use --repo or set GITHUB_REPOSITORY.")
    if not args.token:
        parser.error("GitHub token not provided. Use --token or set GITHUB_TOKEN.")

    issues_dir = Path(args.issues_dir)
    if not issues_dir.exists():
        parser.error(f"Issues directory not found: {issues_dir}")

    local_issues = load_local_issues(issues_dir)
    remote_issues = fetch_remote_issues(args.repo, args.token)

    issues_by_number: dict[int, LocalIssue] = {}
    for issue in local_issues:
        if issue.issue_number is None:
            continue
        if issue.issue_number in issues_by_number:
            existing = issues_by_number[issue.issue_number]
            _log_warning(
                f"⚠️  Duplicate mapping for GitHub issue #{issue.issue_number}:"
                f" {existing.path} and {issue.path}."
            )
        else:
            issues_by_number[issue.issue_number] = issue

    matched_numbers = set()
    for number, remote in remote_issues.items():
        local = issues_by_number.get(number)
        if local:
            matched_numbers.add(number)
            sync_existing_issue(args.repo, args.token, local, remote)
        else:
            create_local_issue_from_remote(issues_dir, remote, token=args.token)

    for issue in local_issues:
        if issue.issue_number is None:
            sync_local_without_remote(args.repo, args.token, issue)
        elif issue.issue_number not in matched_numbers:
            # The associated GitHub issue no longer exists; recreate it.
            _log_info(f"♻️  Recreating missing GitHub issue for {issue.path.name}")
            sync_local_without_remote(args.repo, args.token, issue)

    _log_info("✅ Synchronization complete.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
