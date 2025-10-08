import pytest
from pydantic import ValidationError

from egregora.models import MergeConfig
from egregora.types import GroupSlug


def test_merge_config_accepts_aliases() -> None:
    config = MergeConfig(
        name="Virtual",
        groups=["group-a", "group-b"],
        emojis={"group-a": "😀"},
        tag_style="prefix",
        model="gemini-pro",
    )

    assert config.source_groups == [GroupSlug("group-a"), GroupSlug("group-b")]
    assert config.group_emojis == {GroupSlug("group-a"): "😀"}
    assert config.model_override == "gemini-pro"


def test_merge_config_requires_source_groups() -> None:
    with pytest.raises(ValidationError):
        MergeConfig(name="Virtual", groups=[])


def test_merge_config_rejects_invalid_tag_style() -> None:
    with pytest.raises(ValidationError):
        MergeConfig(name="Virtual", groups=["group-a"], tag_style="unknown")


def test_merge_config_rejects_invalid_emoji_mapping() -> None:
    with pytest.raises(ValidationError):
        MergeConfig(name="Virtual", groups=["group-a"], emojis=["😀"])
