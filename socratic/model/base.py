import datetime

import typing as t

import pydantic as p
from pydantic.main import IncEx


class BaseModel(p.BaseModel):
    def model_dump(
        self,
        *,
        mode: t.Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
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


class WithCtime(BaseModel):
    create_time: datetime.datetime


class WithMtime(BaseModel):
    update_time: datetime.datetime


class WithTimestamps(WithCtime, WithMtime): ...
