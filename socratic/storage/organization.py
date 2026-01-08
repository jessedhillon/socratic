from __future__ import annotations

import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import Organization, OrganizationID

from . import Session
from .table import organizations


def get(key: OrganizationID, session: Session = di.Provide["storage.persistent.session"]) -> Organization | None:
    stmt = select(organizations.__table__).where(organizations.organization_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return Organization(**row) if row else None


def get_by_slug(slug: str, session: Session = di.Provide["storage.persistent.session"]) -> Organization | None:
    stmt = select(organizations.__table__).where(organizations.slug == slug)
    row = session.execute(stmt).mappings().one_or_none()
    return Organization(**row) if row else None


def find(*, session: Session = di.Provide["storage.persistent.session"]) -> tuple[Organization, ...]:
    stmt = select(organizations.__table__)
    rows = session.execute(stmt).mappings().all()
    return tuple(Organization(**row) for row in rows)


def create(
    params: OrganizationCreateParams, session: Session = di.Provide["storage.persistent.session"]
) -> Organization:
    org = organizations(
        organization_id=OrganizationID(),
        name=params["name"],
        slug=params["slug"],
    )
    session.add(org)
    session.flush()
    return get(org.organization_id, session=session)  # type: ignore


class OrganizationCreateParams(t.TypedDict):
    name: str
    slug: str
