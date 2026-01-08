import importlib
import sys
import types
import typing as t

from sqlalchemy.orm import Session, SessionTransaction

__all__ = [
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
]

if t.TYPE_CHECKING:
    from . import assignment, attempt, evaluation, example, objective, organization, override, rubric, strand, \
        transcript, user


def __getattr__(name: str) -> types.ModuleType:
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        setattr(sys.modules[__name__], name, module)
        return module
    raise AttributeError(f"module {__name__} has no attribute {name}")
