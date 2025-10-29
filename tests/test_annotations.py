import sys
from importlib import util
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
PRIVACY_PATH = PROJECT_SRC / "egregora" / "privacy.py"
ANNOTATIONS_PATH = PROJECT_SRC / "egregora" / "annotations.py"

privacy_spec = util.spec_from_file_location("egregora.privacy", PRIVACY_PATH)
assert privacy_spec and privacy_spec.loader  # noqa: S101 - ensure spec is valid for mypy
privacy_module = util.module_from_spec(privacy_spec)
sys.modules.setdefault("egregora", ModuleType("egregora"))
sys.modules["egregora.privacy"] = privacy_module
privacy_spec.loader.exec_module(privacy_module)

annotations_spec = util.spec_from_file_location("egregora.annotations", ANNOTATIONS_PATH)
assert annotations_spec and annotations_spec.loader  # noqa: S101 - ensure spec is valid for mypy
annotations_module = util.module_from_spec(annotations_spec)
sys.modules["egregora.annotations"] = annotations_module
annotations_spec.loader.exec_module(annotations_module)

AnnotationStore = annotations_module.AnnotationStore
EXPECTED_TOTAL_ANNOTATIONS = 3


def test_annotation_store_persists_and_orders(tmp_path):
    db_path = tmp_path / "annotations.duckdb"
    store = AnnotationStore(db_path)

    first = store.save_annotation("msg-1", "First insight")
    second = store.save_annotation(
        "msg-1", "Follow-up", parent_annotation_id=first.id
    )
    third = store.save_annotation("msg-2", "Another message note")

    annotations_msg1 = store.list_annotations_for_message("msg-1")
    assert [annotation.id for annotation in annotations_msg1] == [first.id, second.id]
    assert annotations_msg1[1].parent_annotation_id == first.id

    assert store.get_last_annotation_id("msg-1") == second.id
    assert store.get_last_annotation_id("msg-unknown") is None

    all_annotations = list(store.iter_all_annotations())
    assert len(all_annotations) == EXPECTED_TOTAL_ANNOTATIONS
    assert {annotation.id for annotation in all_annotations} == {
        first.id,
        second.id,
        third.id,
    }


def test_annotation_store_rejects_missing_parent(tmp_path):
    db_path = tmp_path / "annotations.duckdb"
    store = AnnotationStore(db_path)

    with pytest.raises(ValueError):
        store.save_annotation("msg-1", "orphan", parent_annotation_id=999)
