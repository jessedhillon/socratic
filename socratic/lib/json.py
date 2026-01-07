from __future__ import annotations

import base64
import datetime
import decimal
import enum
import functools
import json as pyjson
import pathlib
import typing as t

import fastapi
import pydantic as p
import starlette.background

import socratic.lib.uuid as uuid

JSONPrimitive = str | int | float | bool | None
JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]


# encoders
def encode_bytes(obj: bytes) -> str:
    return base64.b64encode(obj).decode("utf8")


def encode_set(obj: set[t.Any]) -> list[t.Any]:
    return list(obj)


def encode_datetime(obj: datetime.datetime) -> str:
    return obj.isoformat()


def encode_date(obj: datetime.date) -> str:
    return obj.isoformat()


def encode_decimal(obj: decimal.Decimal) -> str:
    return str(obj)


def encode_enum(obj: enum.Enum) -> str:
    return obj.value


def encode_path(obj: pathlib.Path) -> str:
    return str(obj)


def encode_pydantic(obj: p.BaseModel) -> dict[str, JSONValue]:
    return obj.model_dump()


def encode_timedelta(obj: datetime.timedelta) -> int:
    return obj.seconds


def encode_uuid(obj: uuid.UUID) -> str:
    return str(obj)


@functools.cache  # noqa: E302
def _encoder_map() -> dict[type, t.Callable[[t.Any], JSONValue]]:
    import datetime
    import decimal
    import enum
    import pathlib

    import socratic.lib.uuid as uuid

    return {
        bytes: encode_bytes,
        datetime.date: encode_date,
        datetime.datetime: encode_datetime,
        datetime.timedelta: encode_timedelta,
        decimal.Decimal: encode_decimal,
        enum.Enum: encode_enum,
        pathlib.Path: encode_path,
        set: encode_set,
        uuid.UUID: encode_uuid,
    }


# stdlib-compatible JSON encoder
class JSONEncoder(pyjson.JSONEncoder):
    def get_encoders(self) -> dict[type, t.Callable[[t.Any], JSONValue]]:
        return _encoder_map()

    def default(self, o: t.Any) -> JSONValue:
        if hasattr(o, "model_dump"):
            return encode_pydantic(o)

        encoders = _encoder_map()
        for tp in encoders:
            if isinstance(o, tp):
                encoder = encoders[tp]
                return encoder(o)

        return pyjson.JSONEncoder.default(self, o)


def dumps(
    obj: t.Any,
    *,
    skipkeys: bool = False,
    ensure_ascii: bool = True,
    check_circular: bool = True,
    allow_nan: bool = True,
    cls: type[pyjson.JSONEncoder] = JSONEncoder,
    indent: int | str | None = None,
    separators: tuple[str, str] | None = None,
    default: t.Callable[[t.Any], JSONValue] | None = None,
    sort_keys: bool = False,
    **kw: t.Any,
) -> str:
    return pyjson.dumps(
        obj,
        skipkeys=skipkeys,
        ensure_ascii=ensure_ascii,
        check_circular=check_circular,
        allow_nan=allow_nan,
        cls=cls,
        indent=indent,
        separators=separators,
        default=default,
        sort_keys=sort_keys,
        **kw,
    )


def loads(
    s: str | bytes | bytearray,
    *,
    cls: type[pyjson.JSONDecoder] | None = None,
    object_hook: t.Callable[[dict[t.Any, t.Any]], t.Any] | None = None,
    parse_float: t.Callable[[str], t.Any] | None = None,
    parse_int: t.Callable[[str], t.Any] | None = None,
    parse_constant: t.Callable[[str], t.Any] | None = None,
    object_pairs_hook: t.Callable[[list[tuple[t.Any, t.Any]]], t.Any] | None = None,
    **kwds: t.Any,
) -> JSONValue:
    """implemented for parity's sake"""
    return pyjson.loads(
        s,
        cls=cls,
        object_hook=object_hook,
        parse_float=parse_float,
        parse_int=parse_int,
        parse_constant=parse_constant,
        object_pairs_hook=object_pairs_hook,
        **kwds,
    )


# FastAPI compatibility
class FastAPIJSONResponse(fastapi.responses.JSONResponse):
    def __init__(
        self,
        content: t.Any,
        status_code: int = 200,
        headers: t.Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: starlette.background.BackgroundTask | None = None,
    ):
        super().__init__(
            jsonable_encoder(content),
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def render(self, content: t.Any) -> bytes:
        return pyjson.dumps(
            content, ensure_ascii=False, cls=JSONEncoder, allow_nan=False, indent=None, separators=(",", ":")
        ).encode("utf-8")


def jsonable_encoder(obj: t.Any) -> JSONValue:
    import fastapi.encoders

    if hasattr(obj, "model_dump"):
        return jsonable_encoder(encode_pydantic(obj))
    return fastapi.encoders.jsonable_encoder(obj, custom_encoder=_encoder_map())
