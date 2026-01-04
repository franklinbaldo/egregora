from __future__ import annotations

from egregora.utils import authors as utils_authors
from egregora.utils import cache as utils_cache
from egregora.utils import exceptions as utils_exceptions


def test_exceptions_shim_exports() -> None:
    assert issubclass(utils_exceptions.CacheError, Exception)
    assert utils_exceptions.DateTimeParsingError is not None
    assert utils_exceptions.InvalidDateTimeInputError is not None


def test_cache_shim_exports() -> None:
    key = utils_cache.make_enrichment_cache_key(kind="url", identifier="test")
    assert isinstance(key, str)
    assert utils_cache.CacheTier.ENRICHMENT.value == "enrichment"


def test_authors_shim_exports() -> None:
    error = utils_authors.AuthorsFileLoadError("path", OSError("boom"))
    assert error.path == "path"
