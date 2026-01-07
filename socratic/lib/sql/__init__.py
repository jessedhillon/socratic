__all__ = [
    "DebugSession",
    "DebugQuery",
    "EnumValuesType",
    "ExtendedOperations",
]

import alembic.operations
from sqlalchemy.dialects.postgresql import ENUM

from .enum import EnumValuesType
from .session import DebugQuery, DebugSession


class ExtendedOperations(alembic.operations.Operations):
    def create_enum_type(self, type_name: str, values: list[str], schema: str | None = None) -> ENUM: ...
    def drop_enum_type(self, type_name: str, values: list[str] | None = None, schema: str | None = None): ...
    def create_extension(
        self,
        extension_name: str,
        checkfirst: bool = False,
        schema: str | None = None,
        version: str | None = None,
    ): ...
    def drop_extension(self, extension_name: str, cascade: bool = False, checkfirst: bool = False): ...
