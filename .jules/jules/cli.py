"""Jules CLI."""

import typer
import json
from jules.scheduler import run_scheduler
from jules.auto_fix import auto_reply_to_jules

app = typer.Typer()
schedule_app = typer.Typer()
app.add_typer(schedule_app, name="schedule")
autofix_app = typer.Typer()
app.add_typer(autofix_app, name="autofix")

@schedule_app.command("tick")
def schedule_tick(
    all: bool = typer.Option(False, "--all", help="Run all enabled prompts regardless of schedule"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not create sessions"),
    prompt_id: str = typer.Option(None, "--prompt-id", help="Run only specific prompt ID"),
):
    """Run the scheduler tick."""
    run_scheduler("tick", run_all=all, dry_run=dry_run, prompt_id=prompt_id)

@autofix_app.command("analyze")
def autofix_analyze(
    pr_number: int = typer.Argument(..., help="PR number to analyze"),
):
    """Analyze a PR and auto-fix with Jules."""
    result = auto_reply_to_jules(pr_number)
    print(json.dumps(result, indent=2))

feedback_app = typer.Typer()
app.add_typer(feedback_app, name="feedback")

@feedback_app.command("loop")
def feedback_loop(
    dry_run: bool = typer.Option(False, "--dry-run", help="Do not create sessions"),
    author: str = typer.Option("app/google-labs-jules", "--author", help="Filter PRs by author")
):
    """Run the feedback loop."""
    from jules.feedback import run_feedback_loop
    run_feedback_loop(dry_run=dry_run, author_filter=author)

if __name__ == "__main__":
    app()
