#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from dateutil import tz
import re
import shutil
from collections import defaultdict

# --- Config ---
TZ = tz.gettz("America/Porto_Velho")

# fonte dos diários (produzidos pelo seu pipeline)
DAILY_SRC = Path("data")

# destino publicado no MkDocs
DOCS_DIR = Path("docs")
DAILY_DST = DOCS_DIR / "reports" / "daily"
WEEKLY_DST = DOCS_DIR / "reports" / "weekly"
MONTHLY_DST = DOCS_DIR / "reports" / "monthly"

# regex para pegar título do diário (primeiro header) e 1º parágrafo para resumo
H1_RE = re.compile(r"^\s*#\s+(.*)$", re.MULTILINE)

def ensure_dirs():
    for p in [DAILY_DST, WEEKLY_DST, MONTHLY_DST]:
        p.mkdir(parents=True, exist_ok=True)

def iter_daily_files():
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
    # após o primeiro header, pega o primeiro parágrafo “real”
    # simples: divide por linhas em branco
    parts = re.split(r"\n\s*\n", text.strip())
    for chunk in parts:
        # ignora headers/linhas de navegação
        if chunk.strip().startswith("#"):
            continue
        # devolve a primeira parte com algum conteúdo
        if chunk.strip():
            return chunk.strip()
    return None

def copy_daily_to_docs():
    for src in iter_daily_files():
        dt = parse_date_from_path(src)
        dst_dir = DAILY_DST / f"{dt:%Y}" / f"{dt:%m}"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{dt:%d}.md"
        shutil.copy2(src, dst)

def build_weekly_and_monthly():
    # agrupa por (YYYY-ISOweek) e por (YYYY-MM)
    by_week = defaultdict(list)
    by_month = defaultdict(list)

    for daily in sorted(iter_daily_files(), key=lambda p: parse_date_from_path(p)):
        dt = parse_date_from_path(daily)
        iso_year, iso_week, _ = dt.isocalendar()
        by_week[(iso_year, iso_week)].append(daily)
        by_month[(dt.year, dt.month)].append(daily)

    # gerar semanais
    for (y, w), files in by_week.items():
        out_dir = WEEKLY_DST / f"{y}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{y}-W{w:02d}.md"
        body = []
        body.append(f"# Semana {y}-W{w:02d}\n")
        body.append("## Dias\n")
        for f in files:
            dt = parse_date_from_path(f)
            rel = f"../../daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
            text = read_text(f)
            title = first_h1(text) or f"Diário {dt:%Y-%m-%d}"
            # pequeno resumo (opcional)
            summary = first_paragraph(text)
            body.append(f"- **{dt:%a, %d/%m}** — [{title}]({rel})")
            if summary:
                # detalhe recolhível
                body.append(f"  <details><summary>Resumo</summary>\n\n{summary}\n\n</details>")
        out.write_text("\n".join(body) + "\n", encoding="utf-8")

    # gerar mensais
    for (y, m), files in by_month.items():
        out_dir = MONTHLY_DST / f"{y}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{y}-{m:02d}.md"
        month_name = datetime(y, m, 1).strftime("%B").capitalize()
        body = []
        body.append(f"# {month_name} de {y}\n")
        body.append("## Dias\n")
        for f in files:
            dt = parse_date_from_path(f)
            rel = f"../../daily/{dt:%Y}/{dt:%m}/{dt:%d}.md"
            text = read_text(f)
            title = first_h1(text) or f"Diário {dt:%Y-%m-%d}"
            summary = first_paragraph(text)
            body.append(f"- **{dt:%a, %d/%m}** — [{title}]({rel})")
            if summary:
                body.append(f"  <details><summary>Resumo</summary>\n\n{summary}\n\n</details>")
        out.write_text("\n".join(body) + "\n", encoding="utf-8")

def build_section_indexes():
    # Índice de diários
    daily_index = ["# Relatórios Diários\n"]
    for year_dir in sorted((DAILY_DST).glob("[0-9][0-9][0-9][0-9]")):
        year = year_dir.name
        daily_index.append(f"## {year}")
        for month_dir in sorted(year_dir.glob("[0-1][0-9]")):
            month = month_dir.name
            links = []
            for md in sorted(month_dir.glob("[0-3][0-9].md")):
                d = md.stem
                label = f"{d}/{month}/{year}"
                rel = md.relative_to(DOCS_DIR).as_posix()
                links.append(f"[{label}](/{rel})")
            if links:
                daily_index.append(f"- **{year}-{month}**: " + " • ".join(links))
    (DAILY_DST / "index.md").write_text("\n".join(daily_index) + "\n", encoding="utf-8")

    # Índice semanal
    weekly_index = ["# Relatórios Semanais\n"]
    for year_dir in sorted((WEEKLY_DST).glob("[0-9][0-9][0-9][0-9]")):
        year = year_dir.name
        weekly_index.append(f"## {year}")
        items = []
        for md in sorted(year_dir.glob("*.md")):
            rel = md.relative_to(DOCS_DIR).as_posix()
            items.append(f"[{md.stem}](/{rel})")
        if items:
            weekly_index.append("- " + " • ".join(items))
    (WEEKLY_DST / "index.md").write_text("\n".join(weekly_index) + "\n", encoding="utf-8")

    # Índice mensal
    monthly_index = ["# Relatórios Mensais\n"]
    for year_dir in sorted((MONTHLY_DST).glob("[0-9][0-9][0-9][0-9]")):
        year = year_dir.name
        monthly_index.append(f"## {year}")
        items = []
        for md in sorted(year_dir.glob("*.md")):
            rel = md.relative_to(DOCS_DIR).as_posix()
            items.append(f"[{md.stem}](/{rel})")
        if items:
            monthly_index.append("- " + " • ".join(items))
    (MONTHLY_DST / "index.md").write_text("\n".join(monthly_index) + "\n", encoding="utf-8")

def main():
    ensure_dirs()
    copy_daily_to_docs()
    build_weekly_and_monthly()
    build_section_indexes()
    print("OK: diários copiados; semanais/mensais e índices gerados.")

if __name__ == "__main__":
    main()
