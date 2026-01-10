"""CLI commands for managing users and organizations."""

from __future__ import annotations

import secrets

import pydantic as p
from sqlalchemy.orm import Session

import socratic.lib.cli as click
from socratic.core import di
from socratic.model import UserRole
from socratic.storage import organization as org_storage
from socratic.storage import user as user_storage
from socratic.storage.user import MembershipCreateParams


@click.group("user")
def user():
    """Manage users and organizations."""
    ...


@user.command("create")
@click.argument("email")
@click.argument("name")
@click.option("--org", "-o", "org_slug", required=True, help="Organization slug to add user to")
@click.option(
    "--role",
    "-r",
    type=click.Choice(["educator", "learner"]),
    required=True,
    help="User role in the organization",
)
@click.option("--password", "-p", help="Password (if not provided, a random one is generated)")
@di.inject
def user_create(
    email: str,
    name: str,
    org_slug: str,
    role: str,
    password: str | None,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Create a new user and add them to an organization.

    EMAIL is the user's email address (used for login).
    NAME is the user's display name.
    """
    # Generate password if not provided
    generated_password = None
    if not password:
        generated_password = secrets.token_urlsafe(12)
        password = generated_password

    user_role = UserRole(role)

    with session.begin():
        # Validate organization
        organization = org_storage.get(slug=org_slug, session=session)
        if not organization:
            click.echo(f"Error: Organization '{org_slug}' not found.", err=True)
            raise SystemExit(1)

        # Check if email already exists
        existing = user_storage.get(email=email, session=session)
        if existing:
            click.echo(f"Error: User with email '{email}' already exists.", err=True)
            raise SystemExit(1)

        # Create user (password is hashed internally)
        new_user = user_storage.create(
            email=email,
            name=name,
            password=p.Secret(password),
            session=session,
        )

        # Add to organization
        user_storage.update(
            new_user.user_id,
            add_memberships={MembershipCreateParams(organization_id=organization.organization_id, role=user_role)},
            session=session,
        )

    click.echo(f"Created user: {new_user.name}")
    click.echo(f"  ID: {new_user.user_id}")
    click.echo(f"  Email: {new_user.email}")
    click.echo(f"  Organization: {organization.name} ({user_role.value})")
    if generated_password:
        click.echo(f"  Generated password: {generated_password}")


@user.command("create-org")
@click.argument("name")
@click.argument("slug")
@di.inject
def user_create_org(
    name: str,
    slug: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Create a new organization.

    NAME is the display name for the organization.
    SLUG is a URL-friendly identifier (e.g., 'acme-corp').
    """
    with session.begin():
        # Check if slug already exists
        existing = org_storage.get(slug=slug, session=session)
        if existing:
            click.echo(f"Error: Organization with slug '{slug}' already exists.", err=True)
            raise SystemExit(1)

        organization = org_storage.create(name=name, slug=slug, session=session)

    click.echo(f"Created organization: {organization.name}")
    click.echo(f"  ID: {organization.organization_id}")
    click.echo(f"  Slug: {organization.slug}")


@user.command("show")
@click.argument("identifier")
@di.inject
def user_show(
    identifier: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Show details for a user or organization.

    IDENTIFIER can be:
    - An email address (shows user details)
    - An organization slug (shows organization and its members)
    """
    # Try as email first (contains @)
    if "@" in identifier:
        _show_user(identifier, session)
    else:
        # Try as organization slug
        _show_organization(identifier, session)


def _show_user(email: str, session: Session) -> None:
    """Show user details."""
    found_user = user_storage.get(email=email, with_memberships=True, session=session)
    if not found_user:
        click.echo(f"Error: User '{email}' not found.", err=True)
        raise SystemExit(1)

    click.echo(f"User: {found_user.name}")
    click.echo(f"  ID: {found_user.user_id}")
    click.echo(f"  Email: {found_user.email}")
    click.echo(f"  Created: {found_user.create_time}")

    # List memberships
    if found_user.memberships:
        click.echo("\nOrganizations:")
        for m in found_user.memberships:
            organization = org_storage.get(organization_id=m.organization_id, session=session)
            org_name = organization.name if organization else "Unknown"
            click.echo(f"  - {org_name} [{m.role.value}]")


def _show_organization(slug: str, session: Session) -> None:
    """Show organization details."""
    organization = org_storage.get(slug=slug, session=session)
    if not organization:
        click.echo(f"Error: Organization '{slug}' not found.", err=True)
        raise SystemExit(1)

    click.echo(f"Organization: {organization.name}")
    click.echo(f"  ID: {organization.organization_id}")
    click.echo(f"  Slug: {organization.slug}")
    click.echo(f"  Created: {organization.create_time}")

    # List members
    found_users = user_storage.find(organization_id=organization.organization_id, session=session)
    if found_users:
        click.echo(f"\nMembers ({len(found_users)}):")
        for u in found_users:
            user_with_memberships = user_storage.get(user_id=u.user_id, with_memberships=True, session=session)
            if user_with_memberships:
                role = next(
                    (
                        m.role
                        for m in user_with_memberships.memberships
                        if m.organization_id == organization.organization_id
                    ),
                    None,
                )
                click.echo(f"  - {u.name} ({u.email}) [{role.value if role else 'unknown'}]")
    else:
        click.echo("\nNo members.")


@user.command("list")
@click.option("--org", "-o", "org_slug", help="Filter by organization slug")
@click.option("--role", "-r", type=click.Choice(["educator", "learner"]), help="Filter by role")
@di.inject
def user_list(
    org_slug: str | None,
    role: str | None,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """List users, optionally filtered by organization or role."""
    organization_id = None
    if org_slug:
        organization = org_storage.get(slug=org_slug, session=session)
        if not organization:
            click.echo(f"Error: Organization '{org_slug}' not found.", err=True)
            raise SystemExit(1)
        organization_id = organization.organization_id

    user_role = UserRole(role) if role else None
    users = user_storage.find(organization_id=organization_id, role=user_role, session=session)

    if not users:
        click.echo("No users found.")
        return

    click.echo(f"{'ID':<30} {'Name':<25} {'Email':<30}")
    click.echo("-" * 85)
    for u in users:
        click.echo(f"{str(u.user_id):<30} {u.name:<25} {u.email:<30}")


@user.command("enroll")
@click.argument("email")
@click.argument("org_slug")
@click.option(
    "--role",
    "-r",
    type=click.Choice(["educator", "learner"]),
    required=True,
    help="User role in the organization",
)
@di.inject
def user_enroll(
    email: str,
    org_slug: str,
    role: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Enroll an existing user into an organization.

    EMAIL is the user's email address.
    ORG_SLUG is the organization's slug.
    """
    user_role = UserRole(role)

    with session.begin():
        found_user = user_storage.get(email=email, with_memberships=True, session=session)
        if not found_user:
            click.echo(f"Error: User '{email}' not found.", err=True)
            raise SystemExit(1)

        organization = org_storage.get(slug=org_slug, session=session)
        if not organization:
            click.echo(f"Error: Organization '{org_slug}' not found.", err=True)
            raise SystemExit(1)

        # Check if already a member
        if any(m.organization_id == organization.organization_id for m in found_user.memberships):
            click.echo(f"Error: User is already a member of '{org_slug}'.", err=True)
            raise SystemExit(1)

        user_storage.update(
            found_user.user_id,
            add_memberships={MembershipCreateParams(organization_id=organization.organization_id, role=user_role)},
            session=session,
        )

    click.echo(f"Enrolled {found_user.name} in {organization.name} as {user_role.value}")


@user.command("reset-password")
@click.argument("email")
@click.option("--password", "-p", help="New password (if not provided, a random one is generated)")
@di.inject
def user_reset_password(
    email: str,
    password: str | None,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Reset a user's password.

    EMAIL is the user's email address.
    """
    # Generate password if not provided
    generated_password = None
    if not password:
        generated_password = secrets.token_urlsafe(12)
        password = generated_password

    with session.begin():
        found_user = user_storage.get(email=email, session=session)
        if not found_user:
            click.echo(f"Error: User '{email}' not found.", err=True)
            raise SystemExit(1)

        try:
            updated_user = user_storage.update(
                found_user.user_id,
                password=p.Secret(password),
                with_memberships=False,
                session=session,
            )
        except KeyError as e:
            click.echo("Error: Failed to update password.", err=True)
            raise SystemExit(1) from e

    click.echo(f"Password reset for {updated_user.name} ({updated_user.email})")
    if generated_password:
        click.echo(f"  New password: {generated_password}")


command = user
