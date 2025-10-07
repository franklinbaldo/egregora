#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from dateutil import tz
import re
import shutil
from collections import defaultdict

PLACEHOLDER_BUTTON_START = "<!-- LATEST_DAILY_BUTTON -->"
PLACEHOLDER_BUTTON_END = "<!-- /LATEST_DAILY_BUTTON -->"
PLACEHOLDER_CONTENT_START = "<!-- LATEST_DAILY_CONTENT -->"
PLACEHOLDER_CONTENT_END = "<!-- /LATEST_DAILY_CONTENT -->"

# --- Config ---
TZ = tz.gettz("America/Porto_Velho")
LANGUAGES = ["en", "pt-BR"]
DAILY_SRC = Path("data")
DOCS_DIR = Path("docs")
H1_RE = re.compile(r"^\s*#\s+(.*)$", re.MULTILINE)

def iter_daily_files():
    """Yield daily reports from the source data directory."""
    for md in sorted(DAILY_SRC.glob("*/daily/*.md")):
        if md.is_file():
            yield md

def parse_date_from_path(p: Path) -> datetime:
    """Extract a date from either ISO-stemmed files or generated daily paths."""

    try:
        return datetime.fromisoformat(p.stem).replace(tzinfo=TZ)
    except ValueError:
        pass

    # Generated daily report paths live under YYYY/MM/DD.md directories.
    day_name = p.stem
    month_dir = p.parent
    year_dir = month_dir.parent

    if (
        day_name.isdigit()
        and len(day_name) <= 2
        and month_dir.name.isdigit()
        and len(month_dir.name) == 2
        and year_dir.name.isdigit()
        and len(year_dir.name) == 4
    ):
        try:
            return datetime(
                int(year_dir.name), int(month_dir.name), int(day_name), tzinfo=TZ
            )
        except ValueError:
            pass

    raise ValueError(f"Unable to parse date from path: {p}")

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def first_h1(text: str) -> str | None:
    m = H1_RE.search(text)
    return m.group(1).strip() if m else None

def first_paragraph(text: str) -> str | None:
    parts = re.split(r"\n\s*\n", text.strip())
    for chunk in parts:
        if chunk.strip().startswith("#"):
            continue
        if chunk.strip():
            return chunk.strip()
    return None

def _replace_block(text: str, start_marker: str, end_marker: str, new_content: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_marker)}\s*)(.*?)(\s*{re.escape(end_marker)})",
        re.DOTALL,
    )
    def _repl(match: re.Match[str]) -> str:
        leading, trailing = match.group(1), match.group(3)
        return f"{leading}{new_content}{trailing}"
    return pattern.sub(_repl, text)

def ensure_dirs(dirs: list[Path]):
    for p in dirs:
        p.mkdir(parents=True, exist_ok=True)

def copy_daily_to_docs(daily_dst: Path):
    for src in iter_daily_files():
        dt = parse_date_from_path(src)
        dst_dir = daily_dst / f"{dt:%Y}" / f"{dt:%m}"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{dt:%d}.md"
        shutil.copy2(src, dst)

def build_weekly_and_monthly(lang: str, daily_dst: Path, weekly_dst: Path, monthly_dst: Path):
    by_week = defaultdict(list)
    by_month = defaultdict(list)

    # Use the generated daily files for the current language as the source
    for daily in sorted(daily_dst.glob("*/*/*.md"), key=parse_date_from_path):
        dt = parse_date_from_path(daily)
        iso_year, iso_week, _ = dt.isocalendar()
        by_week[(iso_year, iso_week)].append(daily)
        by_month[(dt.year, dt.month)].append(daily)

    # Generate weekly reports
    for (y, w), files in by_week.items():
        out_dir = weekly_dst / f"{y}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{y}-W{w:02d}.md"
        body = [f"# Week {y}-W{w:02d}" if lang == "en" else f"# Semana {y}-W{w:02d}", "## Days" if lang == "en" else "## Dias"]
        for f in files:
            dt = parse_date_from_path(f)
            rel = f"../../daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
            text = read_text(f)
            title = first_h1(text) or (f"Diary {dt:%Y-%m-%d}" if lang == "en" else f"Diário {dt:%Y-%m-%d}")
            summary = first_paragraph(text)
            body.append(f"- **{dt:%a, %d/%m}** — [{title}]({rel})")
            if summary:
                summary_text = "Summary" if lang == "en" else "Resumo"
                body.append(f"  <details><summary>{summary_text}</summary>\n\n{summary}\n\n</details>")
        out.write_text("\n".join(body) + "\n", encoding="utf-8")

    # Generate monthly reports
    for (y, m), files in by_month.items():
        out_dir = monthly_dst / f"{y}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{y}-{m:02d}.md"
        month_name = datetime(y, m, 1).strftime("%B").capitalize()
        body = [f"# {month_name} {y}" if lang == "en" else f"# {month_name} de {y}", "## Days" if lang == "en" else "## Dias"]
        for f in files:
            dt = parse_date_from_path(f)
            rel = f"../../daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
            text = read_text(f)
            title = first_h1(text) or (f"Diary {dt:%Y-%m-%d}" if lang == "en" else f"Diário {dt:%Y-%m-%d}")
            summary = first_paragraph(text)
            body.append(f"- **{dt:%a, %d/%m}** — [{title}]({rel})")
            if summary:
                summary_text = "Summary" if lang == "en" else "Resumo"
                body.append(f"  <details><summary>{summary_text}</summary>\n\n{summary}\n\n</details>")
        out.write_text("\n".join(body) + "\n", encoding="utf-8")

def build_section_indexes(lang: str, daily_dst: Path, weekly_dst: Path, monthly_dst: Path):
    # Daily Index
    daily_title = "# Daily Reports" if lang == "en" else "# Relatórios Diários"
    daily_index = [f"{daily_title}\n"]
    for year_dir in sorted(daily_dst.glob("[0-9]*")):
        year = year_dir.name
        daily_index.append(f"## {year}")
        for month_dir in sorted(year_dir.glob("[0-9]*")):
            month = month_dir.name
            links = [f"[{md.stem}/{month}/{year}]({md.relative_to(daily_dst).as_posix()})" for md in sorted(month_dir.glob("*.md"))]
            if links:
                daily_index.append(f"- **{year}-{month}**: " + " • ".join(links))
    (daily_dst / "index.md").write_text("\n".join(daily_index) + "\n", encoding="utf-8")

    # Weekly Index
    weekly_title = "# Weekly Reports" if lang == "en" else "# Relatórios Semanais"
    weekly_index = [f"{weekly_title}\n"]
    for year_dir in sorted(weekly_dst.glob("[0-9]*")):
        year = year_dir.name
        weekly_index.append(f"## {year}")
        links = [f"[{md.stem}]({md.relative_to(weekly_dst).as_posix()})" for md in sorted(year_dir.glob("*.md"))]
        if links:
            weekly_index.append("- " + " • ".join(links))
    (weekly_dst / "index.md").write_text("\n".join(weekly_index) + "\n", encoding="utf-8")

    # Monthly Index
    monthly_title = "# Monthly Reports" if lang == "en" else "# Relatórios Mensais"
    monthly_index = [f"{monthly_title}\n"]
    for year_dir in sorted(monthly_dst.glob("[0-9]*")):
        year = year_dir.name
        monthly_index.append(f"## {year}")
        links = [f"[{md.stem}]({md.relative_to(monthly_dst).as_posix()})" for md in sorted(year_dir.glob("*.md"))]
        if links:
            monthly_index.append("- " + " • ".join(links))
    (monthly_dst / "index.md").write_text("\n".join(monthly_index) + "\n", encoding="utf-8")

def _collect_recent_daily(daily_dst: Path, limit: int = 3) -> list[tuple[datetime, str, str, str]]:
    candidates = []
    for path in daily_dst.glob("*/**/*.md"):
        if path.name == "index.md":
            continue
        try:
            dt = parse_date_from_path(path)
        except ValueError:
            continue
        rel_path = path.relative_to(daily_dst)
        label = dt.strftime("%d/%m/%Y")
        slug = rel_path.with_suffix("").as_posix()
        candidates.append((dt, label, slug, rel_path.as_posix()))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[:limit]

def _update_homepage(lang: str, daily_dst: Path):
    index_path = DOCS_DIR / lang / "index.md"
    if not index_path.exists():
        return

    recent_daily = _collect_recent_daily(daily_dst)
    text = index_path.read_text(encoding="utf-8")

    if recent_daily:
        _, latest_label, latest_slug, _ = recent_daily[0]
        button_text = f"Report of {latest_label}" if lang == "en" else f"Relatório de {latest_label}"
        more_link_text = "Open full report →" if lang == "en" else "Abrir relatório completo →"
        no_reports_text = "<p>No reports published yet.</p>" if lang == "en" else "<p>Nenhum relatório publicado ainda.</p>"

        latest_button = (
            f'    <a class="primary" href="reports/daily/{latest_slug}/">\n'
            f'      <span class="twemoji">🆕</span>\n'
            f'      {button_text}\n'
            f'    </a>'
        )
        previews = []
        for _, label, slug, rel in recent_daily:
            report_path = daily_dst / rel
            try:
                report_md = report_path.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                continue
            preview = (
                f'<div class="report-preview">\n'
                f"### {label}\n\n"
                f"{report_md}\n\n"
                f'<p class="more-link"><a href="reports/daily/{slug}/">{more_link_text}</a></p>\n'
                f"</div>"
            )
            previews.append(preview)
        content_block = "\n\n".join(previews) if previews else no_reports_text
    else:
        button_text = "No reports available" if lang == "en" else "Nenhum relatório disponível"
        content_block = "<p>No reports published yet.</p>" if lang == "en" else "<p>Nenhum relatório publicado ainda.</p>"
        latest_button = (
            '    <a class="primary" href="#">\n'
            '      <span class="twemoji">🆕</span>\n'
            f"      {button_text}\n"
            "    </a>"
        )

    text = _replace_block(text, PLACEHOLDER_BUTTON_START, PLACEHOLDER_BUTTON_END, latest_button)
    text = _replace_block(text, PLACEHOLDER_CONTENT_START, PLACEHOLDER_CONTENT_END, content_block)
    index_path.write_text(text, encoding="utf-8")

def main():
    # First, delete existing report directories to ensure a clean build
    for lang in LANGUAGES:
        lang_dir = DOCS_DIR / lang
        shutil.rmtree(lang_dir / "reports", ignore_errors=True)

    # Process for each language
    for lang in LANGUAGES:
        print(f"--- Processing language: {lang} ---")

        daily_dst = DOCS_DIR / lang / "reports" / "daily"
        weekly_dst = DOCS_DIR / lang / "reports" / "weekly"
        monthly_dst = DOCS_DIR / lang / "reports" / "monthly"

        ensure_dirs([daily_dst, weekly_dst, monthly_dst])
        copy_daily_to_docs(daily_dst)
        build_weekly_and_monthly(lang, daily_dst, weekly_dst, monthly_dst)
        build_section_indexes(lang, daily_dst, weekly_dst, monthly_dst)
        _update_homepage(lang, daily_dst)

    print("OK: All reports and indexes generated for all languages.")

if __name__ == "__main__":
    main()