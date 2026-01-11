from __future__ import annotations

import typing as t

import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import Organization, OrganizationID

from . import Session
from .table import organizations


@t.overload
def get(
    organization_id: OrganizationID,
    *,
    session: Session = ...,
) -> Organization | None: ...


@t.overload
def get(
    organization_id: None = ...,
    *,
    slug: str,
    session: Session = ...,
) -> Organization | None: ...


def get(
    organization_id: OrganizationID | None = None,
    *,
    slug: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> Organization | None:
    """Get an organization by ID or slug.

    Exactly one of organization_id or slug must be provided.
    """
    if organization_id is None and slug is None:
        raise ValueError("Either organization_id or slug must be provided")
    if organization_id is not None and slug is not None:
        raise ValueError("Only one of organization_id or slug should be provided")

    if organization_id is not None:
        stmt = sqla.select(organizations.__table__).where(organizations.organization_id == organization_id)
    else:
        stmt = sqla.select(organizations.__table__).where(organizations.slug == slug)

    row = session.execute(stmt).mappings().one_or_none()
    return Organization(**row) if row else None


def find(*, session: Session = di.Provide["storage.persistent.session"]) -> tuple[Organization, ...]:
    """Find all organizations."""
    stmt = sqla.select(organizations.__table__)
    rows = session.execute(stmt).mappings().all()
    return tuple(Organization(**row) for row in rows)


def create(
    *,
    name: str,
    slug: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> Organization:
    """Create a new organization."""
    organization_id = OrganizationID()
    stmt = sqla.insert(organizations).values(
        organization_id=organization_id,
        name=name,
        slug=slug,
    )
    session.execute(stmt)
    session.flush()
    return get(organization_id=organization_id, session=session)  # type: ignore[return-value]


def update(
    organization_id: OrganizationID,
    *,
    name: str | NotSet = NotSet(),
    slug: str | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> Organization:
    """Update an organization.

    Uses NotSet sentinel for parameters where None is not a valid value.

    Raises:
        KeyError: If organization_id does not correspond to an organization
    """
    values: dict[str, t.Any] = {}
    if not isinstance(name, NotSet):
        values["name"] = name
    if not isinstance(slug, NotSet):
        values["slug"] = slug

    if values:
        stmt = sqla.update(organizations).where(organizations.organization_id == organization_id).values(**values)
    else:
        # No-op update to verify organization exists
        stmt = (
            sqla.update(organizations)
            .where(organizations.organization_id == organization_id)
            .values(organization_id=organization_id)
        )

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Organization {organization_id} not found")

    session.flush()
    return get(organization_id=organization_id, session=session)  # type: ignore[return-value]
