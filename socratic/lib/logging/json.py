import json as pyjson
import typing as t

from socratic.lib.json import JSONEncoder as BaseJSONEncoder
from socratic.lib.json import JSONValue


def encode_bytes(obj: bytes) -> str:
    lorig = len(obj)
    h = obj[:64].hex()
    s = " ".join([h[i : i + 2] for i in range(0, 32, 2)])

    if lorig > 64:
        s += " ..."
    return f"[{lorig:5}] {s.upper()}"


class JSONEncoder(BaseJSONEncoder):
    def get_encoders(self) -> dict[type, t.Callable[[t.Any], JSONValue]]:
        return {
            **super().get_encoders(),
            bytes: encode_bytes,
        }

    def default(self, o: t.Any) -> JSONValue:
        try:
            return super().default(o)
        except TypeError:
            return repr(o)


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
) -> JSONValue:
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
) -> t.Any:
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
