import importlib
import sys
import typing as t
import types

from sqlalchemy.orm import Session, SessionTransaction

__all__ = [
    "example",
    "Session",
    "SessionTransaction",
]

if t.TYPE_CHECKING:
    from . import example


def __getattr__(name: str) -> types.ModuleType:
    if name in __all__:
        module = importlib.import_module(f"{__name__}.{name}")
        setattr(sys.modules[__name__], name, module)
        return module
    raise AttributeError(f"module {__name__} has no attribute {name}")
