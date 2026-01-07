import enum
import typing as t

from sqlalchemy.engine import Dialect
from sqlalchemy.sql.type_api import TypeDecorator
from sqlalchemy.types import Enum, String

from socratic.model.id import ShortUUIDKey


class ShortUUIDKeyType(TypeDecorator[ShortUUIDKey]):
    impl = String
    cache_ok = True

    def __init__(self, key_type: type[ShortUUIDKey]):
        self.key_type = key_type
        super().__init__(22)  # length of shortuuid

    def process_bind_param(self, value: ShortUUIDKey | None, dialect: Dialect) -> str | None:
        if value is not None:
            return value.key
        return value

    def process_result_value(self, value: str | None, dialect: Dialect) -> ShortUUIDKey | None:
        if value is not None:
            value = self.key_type(key=value)
        return value


class ValueEnumMapper(object):
    @staticmethod
    def values_callable(en: type[enum.Enum]) -> tuple[t.Any]:
        return tuple(e.value for e in en)

    def _resolve_for_python_type(
        self, python_type: type[t.Any], matched_on: t.Any, matched_on_flattened: t.Any
    ) -> Enum | None:
        return Enum(python_type, values_callable=self.values_callable)
