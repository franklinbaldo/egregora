from textwrap import dedent

import pytest

from egregora.pipeline import process_whatsapp_export


@pytest.mark.asyncio
async def test_process_requires_mkdocs(tmp_path):
    """Processing without a MkDocs scaffold should fail fast."""
    output_dir = tmp_path / "site"

    with pytest.raises(ValueError, match="mkdocs\\.yml"):
        await process_whatsapp_export(
            zip_path=tmp_path / "dummy.zip",
            output_dir=output_dir,
            enable_enrichment=False,
        )


@pytest.mark.asyncio
async def test_process_requires_docs_structure(tmp_path):
    """Processing should fail if docs_dir declared in mkdocs.yml does not exist."""
    output_dir = tmp_path / "site"
    output_dir.mkdir()
    mkdocs_path = output_dir / "mkdocs.yml"
    mkdocs_path.write_text(
        dedent(
            """
            site_name: Test
            docs_dir: docs
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Docs directory not found"):
        await process_whatsapp_export(
            zip_path=tmp_path / "dummy.zip",
            output_dir=output_dir,
            enable_enrichment=False,
        )
