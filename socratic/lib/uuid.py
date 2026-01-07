from __future__ import annotations

import typing as t

import fastapi.encoders
import pydantic as p
import uuid_utils as uuid
from pydantic_core import core_schema


class UUID(uuid.UUID):
    if t.TYPE_CHECKING:
        # uuid_utils.UUID doesn't show up as hashable
        def __hash__(self) -> int: ...

    @classmethod
    def _validate(cls, v: UUID | str | None, _: p.ValidationInfo | None = None) -> UUID | None:
        return UUID(v) if isinstance(v, str) else v

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: p.GetJsonSchemaHandler
    ) -> p.json_schema.JsonSchemaValue:
        field_schema = handler(core_schema)
        field_schema.pop("anyOf", None)  # remove the bytes/str union
        field_schema.update(type="string", format="uuid")
        return field_schema

    @classmethod
    def __get_pydantic_core_schema__(cls, source: t.Any, handler: p.GetCoreSchemaHandler) -> core_schema.CoreSchema:
        json_schema = core_schema.chain_schema([
            core_schema.str_schema(),
            core_schema.with_info_after_validator_function(cls._validate, schema=core_schema.str_schema()),
        ])
        python_schema = core_schema.union_schema([
            # check if it's an instance first before doing any further work
            core_schema.is_instance_schema(UUID),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(UUID),
            ]),
        ])
        serializer = core_schema.plain_serializer_function_ser_schema(UUID.__str__, when_used="json")
        return core_schema.json_or_python_schema(
            json_schema=json_schema, python_schema=python_schema, serialization=serializer
        )


# compatibility with python built-in uuid
def uuid4():
    return UUID(bytes=uuid.uuid4().bytes)


def uuid5(ns: UUID, name: str):
    return UUID(bytes=uuid.uuid5(ns, name).bytes)


NAMESPACE_URL = uuid.NAMESPACE_URL


# OpenAPI code generation still uses the default FastAPI jsonable encoder
fastapi.encoders.ENCODERS_BY_TYPE[UUID] = str
