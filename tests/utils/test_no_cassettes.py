from pathlib import Path


def test_no_recorded_cassettes_committed() -> None:
    """Guardrail: cassettes should be removed in favor of deterministic mocks."""

    cassette_dir = Path(__file__).resolve().parents[1] / "cassettes"
    assert not cassette_dir.exists() or not any(cassette_dir.rglob("*.yaml")), (
        "VCR cassette files found; use pydantic-ai TestModel mocks instead."
    )
