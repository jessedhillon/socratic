from __future__ import annotations

import typing as t

import annotated_types as ant
import pydantic as p
import pydantic_core.core_schema as core_schema
import shortuuid


class ShortUUIDKey(str):
    prefix: t.ClassVar[str]
    separator: t.ClassVar[str]

    @classmethod
    def validate_str(cls, v: ShortUUIDKey | str | None, _: p.ValidationInfo) -> ShortUUIDKey | None:
        return cls(v) if v is not None else v

    @classmethod
    def __get_pydantic_json_schema__(cls, src: t.Any, handler: p.GetJsonSchemaHandler) -> p.json_schema.JsonSchemaValue:
        return {
            "type": "string",
        }

    @classmethod
    def __get_pydantic_core_schema__(cls, src: t.Any, handler: p.GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """
        json_schema: must be str, str must pass constructor validation (see __new__)
        """
        from_str_schema = core_schema.chain_schema([
            core_schema.str_schema(),
            core_schema.with_info_after_validator_function(cls.validate_str, schema=core_schema.str_schema()),
        ])
        to_str = core_schema.plain_serializer_function_ser_schema(cls.__str__)

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(cls),
                from_str_schema,
            ]),
            serialization=to_str,
        )

    @p.validate_call
    def __init_subclass__(cls, prefix: t.Annotated[str, ant.Len(4)], separator: t.Annotated[str, ant.Len(1)] = "$"):
        super.__init_subclass__()
        cls.prefix = prefix
        cls.separator = separator

    def __new__(
        cls,
        s: t.Annotated[str, ant.Len(27)] | None = None,
        /,
        key: t.Annotated[str, ant.Len(22)] | None = None,
    ) -> t.Self:
        """
        s must be a valid key in and of it self (i.e. prefixed already)
        key must be the key-part only (i.e. a shortuuid)

        if key is present, prefix it and use it without validation (fast path
            for marshaling)
        if key is not present, s must be validated if present
        """
        if key is None:
            if s is not None:
                if not s.startswith(cls.prefix + cls.separator):
                    raise ValueError(f"invalid {cls.__name__}: key must begin with {cls.prefix}")
                lpre = len(cls.prefix) + len(cls.separator)
                if len(s) != 22 + lpre:
                    raise ValueError(f"invalid {cls.__name__}: key must have length 22")
                alphabet = shortuuid.get_alphabet()
                if any((c not in alphabet) for c in s[lpre:]):
                    raise ValueError(f"invalid {cls.__name__}: key must comprise only {alphabet}")
                return super().__new__(cls, s)
            key = shortuuid.uuid()
        prefixed = cls.separator.join((cls.prefix, key))
        return super().__new__(cls, prefixed)

    @property
    def key(self) -> str:
        i = len(self.prefix) + len(self.separator)
        return self[i:]

    def __hash__(self) -> int:
        return str.__hash__(self)

    def __str__(self) -> str:
        return str.__str__(self)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.key!s}>"


# fmt: off
class ExampleID(ShortUUIDKey, prefix="example"): ...
