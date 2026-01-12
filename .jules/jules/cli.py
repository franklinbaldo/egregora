"""Jules CLI."""

import typer

from jules.auto_fix import auto_reply_to_jules
from jules.scheduler_managers import BranchManager
from jules.scheduler_v2 import run_scheduler

app = typer.Typer()
schedule_app = typer.Typer()
app.add_typer(schedule_app, name="schedule")
autofix_app = typer.Typer()
app.add_typer(autofix_app, name="autofix")
sync_app = typer.Typer()
app.add_typer(sync_app, name="sync")


@schedule_app.command("tick")
def schedule_tick(
    all: bool = typer.Option(False, "--all", help="Run all enabled prompts regardless of schedule"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not create sessions"),
    prompt_id: str = typer.Option(None, "--prompt-id", help="Run only specific prompt ID or prompt path"),
) -> None:
    """Run the scheduler tick."""
    run_scheduler("tick", run_all=all, dry_run=dry_run, prompt_id=prompt_id)


@autofix_app.command("analyze")
def autofix_analyze(
    pr_number: int = typer.Argument(..., help="PR number to analyze"),
) -> None:
    """Analyze a PR and auto-fix with Jules."""
    auto_reply_to_jules(pr_number)


feedback_app = typer.Typer()
app.add_typer(feedback_app, name="feedback")


@feedback_app.command("loop")
def feedback_loop(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not create sessions"),
    author: str = typer.Option("app/google-labs-jules", "--author", help="Filter PRs by author"),
) -> None:
    """Run the feedback loop."""
    from jules.feedback import run_feedback_loop

    run_feedback_loop(dry_run=dry_run, author_filter=author)


@sync_app.command("merge-main")
def sync_merge_main(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not execute changes"),
) -> None:
    """Directly merge jules → main (no PR)."""
    mgr = BranchManager()
    ok = mgr.merge_jules_into_main_direct(dry_run=dry_run)
    print("Merge completed." if ok else "Merge not completed.")


if __name__ == "__main__":
    app()
