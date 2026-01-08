"""Route aggregation for the Socratic web application."""

from fastapi import APIRouter

from . import assessment, assignment, auth, learner, objective, organization, strand

router = APIRouter()
router.include_router(auth.router)
router.include_router(organization.router)
router.include_router(objective.router)
router.include_router(strand.router)
router.include_router(assignment.router)
router.include_router(learner.router)
router.include_router(assessment.router)
