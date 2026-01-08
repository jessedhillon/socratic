import enum

from pydantic import EmailStr

from .base import BaseModel, WithTimestamps
from .id import OrganizationID, UserID


class UserRole(enum.Enum):
    Educator = "educator"
    Learner = "learner"


class User(BaseModel, WithTimestamps):
    user_id: UserID
    email: EmailStr
    name: str
    password_hash: str | None = None


class OrganizationMembership(BaseModel, WithTimestamps):
    user_id: UserID
    organization_id: OrganizationID
    role: UserRole


class UserWithMemberships(User):
    memberships: list[OrganizationMembership] = []
