"""Route aggregation for the Socratic web application."""

from fastapi import APIRouter

from . import auth, organization

router = APIRouter()
router.include_router(auth.router)
router.include_router(organization.router)
