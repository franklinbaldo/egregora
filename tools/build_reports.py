#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import calendar
import re
import shutil
from typing import Dict, Iterable, List, Tuple

from dateutil import tz

# --- Config ---
TZ = tz.gettz("America/Porto_Velho")

# fonte dos diários (produzidos pelo seu pipeline)
DAILY_SRC = Path("data/newsletters")

# destino publicado no MkDocs
DOCS_DIR = Path("docs")

# regex para pegar título do diário (primeiro header) e 1º parágrafo para resumo
H1_RE = re.compile(r"^\s*#\s+(.*)$", re.MULTILINE)

PT_MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

PT_WEEKDAY_SHORT = {
    0: "Seg",
    1: "Ter",
    2: "Qua",
    3: "Qui",
    4: "Sex",
    5: "Sáb",
    6: "Dom",
}

LanguageConfig = Dict[str, object]

LANGUAGES: Dict[str, LanguageConfig] = {
    "en": {
        "code": "en",
        "docs_dir": DOCS_DIR / "en",
        "home_path": DOCS_DIR / "en" / "index.md",
        "home_empty": "*No reports have been generated yet.*",
        "home_line": "- **{label}** — [{title}]({link}) ({date})",
        "labels": {
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
            "summary": "Summary",
        },
        "daily": {
            "heading": "# Daily Reports",
            "intro": "Every newsletter in this section captures a single day of WhatsApp activity. Use the list below to jump directly to a date.",
            "empty": "*Daily reports will appear here once the pipeline runs.*",
            "marker": "daily",
            "index_path": DOCS_DIR / "en" / "reports" / "daily" / "index.md",
            "year_heading": lambda year: f"## {year}",
            "month_label": lambda year, month: f"{year}-{month:02d}",
            "link_label": lambda dt: dt.strftime("%Y-%m-%d"),
        },
        "weekly": {
            "heading": "# Weekly Reports",
            "intro": "Weekly roundups summarise what happened across ISO weeks. Browse the archive below to review trends.",
            "empty": "*Weekly reports will appear here once the pipeline runs.*",
            "marker": "weekly",
            "index_path": DOCS_DIR / "en" / "reports" / "weekly" / "index.md",
            "year_heading": lambda year: f"## {year}",
            "link_label": lambda year, week: f"Week {year}-W{week:02d}",
            "page_title": lambda year, week: f"Week {year}-W{week:02d}",
            "days_heading": "## Days",
            "entry_label": lambda dt: dt.strftime("%a, %b %d"),
        },
        "monthly": {
            "heading": "# Monthly Reports",
            "intro": "Monthly consolidations collect the highlights from every day in a calendar month.",
            "empty": "*Monthly reports will appear here once the pipeline runs.*",
            "marker": "monthly",
            "index_path": DOCS_DIR / "en" / "reports" / "monthly" / "index.md",
            "year_heading": lambda year: f"## {year}",
            "link_label": lambda year, month: f"{calendar.month_name[month]} {year}",
            "page_title": lambda year, month: f"{calendar.month_name[month]} {year}",
            "days_heading": "## Days",
            "entry_label": lambda dt: dt.strftime("%a, %b %d"),
        },
    },
    "pt-BR": {
        "code": "pt-BR",
        "docs_dir": DOCS_DIR / "pt-BR",
        "home_path": DOCS_DIR / "pt-BR" / "index.md",
        "home_empty": "*Nenhum relatório foi publicado ainda.*",
        "home_line": "- **{label}** — [{title}]({link}) ({date})",
        "labels": {
            "daily": "Diário",
            "weekly": "Semanal",
            "monthly": "Mensal",
            "summary": "Resumo",
        },
        "daily": {
            "heading": "# Relatórios Diários",
            "intro": "Cada boletim diário reflete um dia específico de atividade no WhatsApp.",
            "empty": "*Os relatórios diários aparecerão aqui assim que o pipeline for executado.*",
            "marker": "daily",
            "index_path": DOCS_DIR / "pt-BR" / "reports" / "daily" / "index.md",
            "year_heading": lambda year: f"## {year}",
            "month_label": lambda year, month: f"{year}-{month:02d}",
            "link_label": lambda dt: dt.strftime("%d/%m/%Y"),
        },
        "weekly": {
            "heading": "# Relatórios Semanais",
            "intro": "As consolidações semanais agregam os boletins diários de cada semana ISO.",
            "empty": "*Os relatórios semanais aparecerão aqui assim que o pipeline for executado.*",
            "marker": "weekly",
            "index_path": DOCS_DIR / "pt-BR" / "reports" / "weekly" / "index.md",
            "year_heading": lambda year: f"## {year}",
            "link_label": lambda year, week: f"Semana {year}-W{week:02d}",
            "page_title": lambda year, week: f"Semana {year}-W{week:02d}",
            "days_heading": "## Dias",
            "entry_label": lambda dt: f"{dt:%d/%m} ({PT_WEEKDAY_SHORT[dt.weekday()]})",
        },
        "monthly": {
            "heading": "# Relatórios Mensais",
            "intro": "Os boletins mensais concentram os principais acontecimentos de cada mês calendário.",
            "empty": "*Os relatórios mensais aparecerão aqui assim que o pipeline for executado.*",
            "marker": "monthly",
            "index_path": DOCS_DIR / "pt-BR" / "reports" / "monthly" / "index.md",
            "year_heading": lambda year: f"## {year}",
            "link_label": lambda year, month: f"{PT_MONTH_NAMES[month]} de {year}",
            "page_title": lambda year, month: f"{PT_MONTH_NAMES[month]} de {year}",
            "days_heading": "## Dias",
            "entry_label": lambda dt: dt.strftime("%d/%m"),
        },
    },
}


def iter_daily_files() -> Iterable[Path]:
    """Yield daily reports stored under the group-aware layout."""

    for md in sorted(DAILY_SRC.glob("*/daily/*.md")):
        if md.is_file():
            yield md


def parse_date_from_path(p: Path) -> datetime:
    """Extract the ISO date from the filename."""

    return datetime.fromisoformat(p.stem).replace(tzinfo=TZ)


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


def ensure_index_file(config: LanguageConfig, section: str) -> None:
    section_cfg = config[section]
    index_path: Path = section_cfg["index_path"]
    if index_path.exists():
        return
    index_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        section_cfg["heading"],
        "",
        section_cfg["intro"],
        "",
        f"<!-- reports:{section_cfg['marker']}:start -->",
        section_cfg["empty"],
        f"<!-- reports:{section_cfg['marker']}:end -->",
        "",
    ]
    index_path.write_text("\n".join(lines), encoding="utf-8")


def clean_report_directories(config: LanguageConfig, section: str) -> None:
    section_cfg = config[section]
    index_path: Path = section_cfg["index_path"]
    directory = index_path.parent
    directory.mkdir(parents=True, exist_ok=True)
    for item in directory.iterdir():
        if item == index_path:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def replace_block(path: Path, marker: str, lines: List[str]) -> None:
    start = f"<!-- reports:{marker}:start -->"
    end = f"<!-- reports:{marker}:end -->"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    block = start + "\n"
    if lines:
        block += "\n".join(lines) + "\n"
    block += end
    if not pattern.search(text):
        raise ValueError(f"Placeholder markers not found in {path}")
    new_text = pattern.sub(block, text)
    path.write_text(new_text, encoding="utf-8")


def collect_daily_entries() -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for src in iter_daily_files():
        dt = parse_date_from_path(src)
        text = read_text(src)
        title = first_h1(text) or f"Daily {dt:%Y-%m-%d}"
        summary = first_paragraph(text)
        entries.append({
            "path": src,
            "dt": dt,
            "title": title,
            "summary": summary,
        })
    entries.sort(key=lambda item: item["dt"])
    return entries


def copy_daily_reports(config: LanguageConfig, entries: List[Dict[str, object]]) -> None:
    section_cfg = config["daily"]
    dst_root = section_cfg["index_path"].parent
    for entry in entries:
        dt: datetime = entry["dt"]  # type: ignore[assignment]
        dst_dir = dst_root / f"{dt:%Y}" / f"{dt:%m}"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{dt:%d}.md"
        shutil.copy2(entry["path"], dst)  # type: ignore[arg-type]
    print(f"[{config['code']}] Copied {len(entries)} daily reports.")


def build_weekly_and_monthly_groups(entries: List[Dict[str, object]]) -> Tuple[Dict[Tuple[int, int], List[Dict[str, object]]], Dict[Tuple[int, int], List[Dict[str, object]]]]:
    by_week: Dict[Tuple[int, int], List[Dict[str, object]]] = defaultdict(list)
    by_month: Dict[Tuple[int, int], List[Dict[str, object]]] = defaultdict(list)
    for entry in entries:
        dt: datetime = entry["dt"]  # type: ignore[assignment]
        iso_year, iso_week, _ = dt.isocalendar()
        by_week[(iso_year, iso_week)].append(entry)
        by_month[(dt.year, dt.month)].append(entry)
    return by_week, by_month


def build_weekly_reports(config: LanguageConfig, weekly_groups: Dict[Tuple[int, int], List[Dict[str, object]]]) -> None:
    section_cfg = config["weekly"]
    dst_root = section_cfg["index_path"].parent
    for (year, week), entries in sorted(weekly_groups.items()):
        out_dir = dst_root / f"{year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{year}-W{week:02d}.md"
        lines: List[str] = [section_cfg["page_title"](year, week), "", section_cfg["days_heading"], ""]
        for entry in entries:
            dt: datetime = entry["dt"]  # type: ignore[assignment]
            rel = f"../../daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
            title: str = entry["title"]  # type: ignore[assignment]
            summary = entry.get("summary")
            lines.append(f"- **{section_cfg['entry_label'](dt)}** — [{title}]({rel})")
            if summary:
                lines.append(f"  <details><summary>{config['labels']['summary']}</summary>\n\n{summary}\n\n</details>")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{config['code']}] Generated {len(weekly_groups)} weekly reports.")


def build_monthly_reports(config: LanguageConfig, monthly_groups: Dict[Tuple[int, int], List[Dict[str, object]]]) -> None:
    section_cfg = config["monthly"]
    dst_root = section_cfg["index_path"].parent
    for (year, month), entries in sorted(monthly_groups.items()):
        out_dir = dst_root / f"{year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{year}-{month:02d}.md"
        lines: List[str] = [section_cfg["page_title"](year, month), "", section_cfg["days_heading"], ""]
        for entry in entries:
            dt: datetime = entry["dt"]  # type: ignore[assignment]
            rel = f"../../daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
            title: str = entry["title"]  # type: ignore[assignment]
            summary = entry.get("summary")
            lines.append(f"- **{section_cfg['entry_label'](dt)}** — [{title}]({rel})")
            if summary:
                lines.append(f"  <details><summary>{config['labels']['summary']}</summary>\n\n{summary}\n\n</details>")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{config['code']}] Generated {len(monthly_groups)} monthly reports.")


def build_daily_index(config: LanguageConfig, entries: List[Dict[str, object]]) -> None:
    section_cfg = config["daily"]
    ensure_index_file(config, "daily")
    index_path: Path = section_cfg["index_path"]
    lines: List[str] = []
    if entries:
        grouped: Dict[int, Dict[int, List[Dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
        for entry in entries:
            dt: datetime = entry["dt"]  # type: ignore[assignment]
            grouped[dt.year][dt.month].append(entry)
        for year in sorted(grouped):
            if lines:
                lines.append("")
            lines.append(section_cfg["year_heading"](year))
            for month in sorted(grouped[year]):
                month_entries = sorted(grouped[year][month], key=lambda item: item["dt"])
                link_parts = []
                for item in month_entries:
                    dt: datetime = item["dt"]  # type: ignore[assignment]
                    rel = f"{dt:%Y}/{dt:%m}/{dt:%d}.md"
                    label = section_cfg["link_label"](dt)
                    link_parts.append(f"[{label}]({rel})")
                lines.append(f"- **{section_cfg['month_label'](year, month)}**: " + " • ".join(link_parts))
    else:
        lines.append(section_cfg["empty"])
    replace_block(index_path, section_cfg["marker"], lines)


def build_weekly_index(config: LanguageConfig, weekly_groups: Dict[Tuple[int, int], List[Dict[str, object]]]) -> None:
    section_cfg = config["weekly"]
    ensure_index_file(config, "weekly")
    index_path: Path = section_cfg["index_path"]
    lines: List[str] = []
    if weekly_groups:
        grouped: Dict[int, List[Tuple[int, Path]]] = defaultdict(list)
        for (year, week), _entries in weekly_groups.items():
            file_name = Path(f"{year}-W{week:02d}.md")
            grouped[year].append((week, file_name))
        for year in sorted(grouped):
            if lines:
                lines.append("")
            lines.append(section_cfg["year_heading"](year))
            weeks = sorted(grouped[year])
            links = [f"[{section_cfg['link_label'](year, week)}]({year}/{file.name})" for week, file in weeks]
            lines.append("- " + " • ".join(links))
    else:
        lines.append(section_cfg["empty"])
    replace_block(index_path, section_cfg["marker"], lines)


def build_monthly_index(config: LanguageConfig, monthly_groups: Dict[Tuple[int, int], List[Dict[str, object]]]) -> None:
    section_cfg = config["monthly"]
    ensure_index_file(config, "monthly")
    index_path: Path = section_cfg["index_path"]
    lines: List[str] = []
    if monthly_groups:
        grouped: Dict[int, List[Tuple[int, Path]]] = defaultdict(list)
        for (year, month), _entries in monthly_groups.items():
            file_name = Path(f"{year}-{month:02d}.md")
            grouped[year].append((month, file_name))
        for year in sorted(grouped):
            if lines:
                lines.append("")
            lines.append(section_cfg["year_heading"](year))
            months = sorted(grouped[year])
            links = [f"[{section_cfg['link_label'](year, month)}]({year}/{file.name})" for month, file in months]
            lines.append("- " + " • ".join(links))
    else:
        lines.append(section_cfg["empty"])
    replace_block(index_path, section_cfg["marker"], lines)


def update_home_latest(config: LanguageConfig, entries: List[Dict[str, object]], weekly_groups: Dict[Tuple[int, int], List[Dict[str, object]]], monthly_groups: Dict[Tuple[int, int], List[Dict[str, object]]]) -> None:
    path: Path = config["home_path"]
    if not path.exists():
        return
    lines: List[str] = []
    if entries:
        latest_daily = entries[-1]
        dt: datetime = latest_daily["dt"]  # type: ignore[assignment]
        link = f"reports/daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
        title: str = latest_daily["title"]  # type: ignore[assignment]
        lines.append(config["home_line"].format(label=config["labels"]["daily"], title=title, link=link, date=dt.strftime("%Y-%m-%d")))
    if weekly_groups:
        year, week = max(weekly_groups.keys())
        link = f"reports/weekly/{year}/{year}-W{week:02d}.md"
        title = config["weekly"]["page_title"](year, week)
        lines.append(config["home_line"].format(label=config["labels"]["weekly"], title=title, link=link, date=f"{year}-W{week:02d}"))
    if monthly_groups:
        year, month = max(monthly_groups.keys())
        link = f"reports/monthly/{year}/{year}-{month:02d}.md"
        title = config["monthly"]["page_title"](year, month)
        if config["code"] == "pt-BR":
            date_label = f"{PT_MONTH_NAMES[month]} de {year}"
        else:
            date_label = f"{calendar.month_name[month]} {year}"
        lines.append(config["home_line"].format(label=config["labels"]["monthly"], title=title, link=link, date=date_label))
    if not lines:
        lines = [config["home_empty"]]
    replace_block(path, "latest", lines)


def main() -> None:
    entries = collect_daily_entries()
    weekly_groups, monthly_groups = build_weekly_and_monthly_groups(entries)

    for code, config in LANGUAGES.items():
        print(f"Processing language: {code}")
        for section in ("daily", "weekly", "monthly"):
            ensure_index_file(config, section)
            clean_report_directories(config, section)
        copy_daily_reports(config, entries)
        build_weekly_reports(config, weekly_groups)
        build_monthly_reports(config, monthly_groups)
        build_daily_index(config, entries)
        build_weekly_index(config, weekly_groups)
        build_monthly_index(config, monthly_groups)
        update_home_latest(config, entries, weekly_groups, monthly_groups)
    print("OK: reports copied and indexes generated for all languages.")


if __name__ == "__main__":
    main()
