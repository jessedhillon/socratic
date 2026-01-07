from fastapi import APIRouter, Depends

from socratic.core import di
from socratic.model import DeploymentEnvironment

from ..view import HelloView

router = APIRouter(prefix="/api")


@router.get("/", operation_id="index")
@di.inject
def index(
    env: DeploymentEnvironment = Depends(di.Provide["env"]),
) -> HelloView:
    return HelloView(env=env)
