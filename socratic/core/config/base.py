import typing as t

import pydantic as p
from pydantic_settings import BaseSettings as PydanticBaseSettings

from socratic.model import BaseModel


class BaseSettings(PydanticBaseSettings, BaseModel):  # pyright: ignore [reportIncompatibleVariableOverride]
    def __init__(self, cf: dict[str, t.Any] | None = None, **kwargs: t.Any):
        # specifically allow initialization with a dict
        if cf is not None:
            kwargs = {**cf, **kwargs}
        super().__init__(**kwargs)

    def model_dump(
        self,
        *,
        mode: t.Literal["json", "python"] | str = "python",
        include: p.main.IncEx | None = None,
        exclude: p.main.IncEx | None = None,
        context: t.Any | None = None,
        by_alias: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | t.Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, t.Any]:
        # invert default by_alias to True
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )


class BaseSecrets(PydanticBaseSettings, BaseModel):  # pyright: ignore [reportIncompatibleVariableOverride]
    def __init__(self, cf: dict[str, t.Any] | None = None, **kwargs: t.Any):
        # specifically allow initialization with a dict
        if cf is not None:
            kwargs = {**cf, **kwargs}
        super().__init__(**kwargs)

    def model_dump(
        self,
        *,
        mode: t.Literal["json", "python"] | str = "python",
        include: p.main.IncEx | None = None,
        exclude: p.main.IncEx | None = None,
        context: t.Any | None = None,
        by_alias: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | t.Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, t.Any]:
        # invert default by_alias to True
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )
