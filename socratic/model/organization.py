from .base import BaseModel, WithTimestamps
from .id import OrganizationID


class Organization(BaseModel, WithTimestamps):
    organization_id: OrganizationID
    name: str
    slug: str
