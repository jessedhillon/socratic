"""Route aggregation for the Socratic web application."""

from fastapi import APIRouter

from . import auth, objective, organization, strand

router = APIRouter()
router.include_router(auth.router)
router.include_router(organization.router)
router.include_router(objective.router)
router.include_router(strand.router)
