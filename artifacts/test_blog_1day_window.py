"""Test blog generation with Egregora using 1-day time windows.

This script runs the Egregora pipeline with:
- 1-day time windows (step_size=1, step_unit="days")
- Test data from real-whatsapp-export.zip
- Output to /home/frank/workspace/blog-test-{timestamp}
- Enrichment enabled (default)
- Collects potential bugs/improvements during execution
"""

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Log file location within the repo to avoid /tmp warnings.
LOG_PATH = Path("artifacts/egregora_test_run.log")
MAX_POSTS_SHOWN = 10


def _bootstrap_imports() -> tuple[type, type]:
    """Load egregora imports after amending sys.path."""
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from egregora.orchestration.pipelines.write import (
        WhatsAppProcessOptions,
        process_whatsapp_export,
    )
    from egregora.output_adapters.mkdocs.scaffolding import (
        MkDocsSiteScaffolder,
    )

    return WhatsAppProcessOptions, process_whatsapp_export, MkDocsSiteScaffolder


# Set up logging to capture all output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> int | None:
    """Run the test blog generation."""
    (
        whatsapp_process_options_cls,
        process_whatsapp_export,
        mkdocs_site_scaffolder_cls,
    ) = _bootstrap_imports()
    # Generate unique test ID from timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_id = timestamp

    # Paths
    zip_path = Path("/home/frank/workspace/real-whatsapp-export.zip")
    output_dir = Path(f"/home/frank/workspace/blog-test-{test_id}")

    logger.info("=" * 80)
    logger.info("Starting Egregora Blog Test")
    logger.info("=" * 80)
    logger.info(f"Test ID: {test_id}")
    logger.info(f"Input: {zip_path}")
    logger.info(f"Output: {output_dir}")
    logger.info("Window Configuration: 1 day (step_size=1, step_unit='days')")
    logger.info("=" * 80)

    # Validate input exists
    if not zip_path.exists():
        logger.error(f"Input file not found: {zip_path}")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize the site with MkDocs scaffolding
    logger.info("Initializing MkDocs site structure...")
    scaffolder = mkdocs_site_scaffolder_cls()
    scaffolder.scaffold_site(output_dir, site_name=f"blog-test-{test_id}")
    logger.info(f"Site initialized at {output_dir}")

    # Configure pipeline options for 1-day windows
    options = whatsapp_process_options_cls(
        output_dir=output_dir,
        step_size=1,  # 1 day
        step_unit="days",  # Use days as the unit
        overlap_ratio=0.2,  # 20% overlap for context
        enable_enrichment=True,  # Enable URL/media enrichment
        timezone="America/Sao_Paulo",  # BR timezone
        # Note: from_date and to_date are optional - if not set, processes all data
    )

    # Track issues/improvements
    issues_found = []

    try:
        logger.info("Starting blog generation pipeline...")
        result = process_whatsapp_export(zip_path, options=options)

        logger.info("=" * 80)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 80)
        logger.info(f"Results: {result}")
        logger.info(f"Output directory: {output_dir}")
        logger.info("=" * 80)

        # List generated files
        posts_dir = output_dir / "docs" / "posts"
        if posts_dir.exists():
            post_files = list(posts_dir.glob("*.md"))
            logger.info(f"Generated {len(post_files)} blog posts:")
            for post_file in post_files[:MAX_POSTS_SHOWN]:  # Show first 10
                logger.info(f"  - {post_file.name}")
            if len(post_files) > MAX_POSTS_SHOWN:
                logger.info(f"  ... and {len(post_files) - MAX_POSTS_SHOWN} more")

        return 0

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user (Ctrl+C)")
        issues_found.append("INTERRUPTED: User terminated execution")
        return 130

    except Exception as e:
        logger.exception("=" * 80)
        logger.exception("Pipeline failed with exception:")
        logger.exception("=" * 80)
        logger.exception(f"Error type: {type(e).__name__}")
        logger.exception(f"Error message: {e}")
        logger.exception("=" * 80)
        logger.exception("Traceback:")
        traceback.print_exc()
        logger.exception("=" * 80)

        issues_found.append(f"EXCEPTION: {type(e).__name__}: {e}")

        # Save issues to file
        issues_file = output_dir / "ISSUES_FOUND.txt"
        with issues_file.open("w") as f:
            f.write("Issues found during Egregora blog generation:\n")
            f.write("=" * 80 + "\n\n")
            for issue in issues_found:
                f.write(f"- {issue}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write("Full traceback:\n\n")
            f.write(traceback.format_exc())

        logger.exception(f"Issues logged to: {issues_file}")
        return 1

    finally:
        # Always create summary file
        summary_file = output_dir / "TEST_SUMMARY.txt"
        with summary_file.open("w") as f:
            f.write(f"Egregora Blog Test - {test_id}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Input: {zip_path}\n")
            f.write(f"Output: {output_dir}\n")
            f.write("Window: 1 day (step_size=1, step_unit='days')\n")
            f.write("Enrichment: Enabled\n")
            f.write("Timezone: America/Sao_Paulo\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"Issues found: {len(issues_found)}\n")
            if issues_found:
                f.write("\nIssues:\n")
                for issue in issues_found:
                    f.write(f"  - {issue}\n")

        logger.info(f"Test summary saved to: {summary_file}")


if __name__ == "__main__":
    sys.exit(main())
