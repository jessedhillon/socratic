from __future__ import annotations

import typing as t

from sqlalchemy import select

from socratic.model import Example, ExampleID
from socratic.core import di

from .table import example
from . import Session


def get(key: ExampleID, session: Session = di.Provide["storage.persistent.session"]) -> Example | None:
    stmt = select(example.__table__).where(example.example_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return Example(**row) if row else None


def find(*, session: Session = di.Provide["storage.persistent.session"]) -> tuple[Example, ...]:
    raise NotImplementedError


def create(*, session: Session = di.Provide["storage.persistent.session"]) -> Example:
    raise NotImplementedError


def create_many(*params: ExampleCreateParams, session: Session = di.Provide["storage.persistent.session"]) -> Example:
    raise NotImplementedError


def update(*, session: Session = di.Provide["storage.persistent.session"]) -> None:
    raise NotImplementedError


def delete(key: ExampleID, session: Session = di.Provide["storage.persistent.session"]): ...


class ExampleCreateParams(t.TypedDict):
    example_key: ExampleID
