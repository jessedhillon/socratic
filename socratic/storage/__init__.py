import importlib
import sys
import types
import typing as t

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction

__all__ = [
    "AsyncSession",
    "Session",
    "SessionTransaction",
    # Repository modules
    "example",
    "organization",
    "user",
    "objective",
    "strand",
    "rubric",
    "assignment",
    "attempt",
    "transcript",
    "evaluation",
    "override",
    "flight",
]

if t.TYPE_CHECKING:
    from . import assignment, attempt, evaluation, example, flight, objective, organization, override, rubric, strand, \
        transcript, user


def __getattr__(name: str) -> types.ModuleType:
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        setattr(sys.modules[__name__], name, module)
        return module
    raise AttributeError(f"module {__name__} has no attribute {name}")
