from __future__ import annotations

from typing import Any

from ibis import Table

__all__ = ["Table"]


class Column: ...


class Scalar: ...


class Value: ...


class ColumnExpr(Value): ...


class ScalarExpr(Value): ...


class TableExpr(Table): ...

