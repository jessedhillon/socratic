__all__ = [
    "router",
]

from fastapi import APIRouter

from . import example

router = APIRouter()
router.include_router(example.router)
