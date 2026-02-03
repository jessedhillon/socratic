__all__ = [
    "router",
]

from fastapi import APIRouter

from . import flight, survey, template

router = APIRouter()
router.include_router(template.router)
router.include_router(flight.router)
router.include_router(survey.router)
