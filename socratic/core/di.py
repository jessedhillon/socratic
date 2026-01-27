from __future__ import annotations

__all__ = [
    "Closing",
    "Container",
    "NotReady",
    "Provider",
    "Provide",
    "as_",
    "as_int",
    "as_float",
    "inject",
    "providers",
    "containers",
    "register_loader_containers",
    "required",
]

import functools
import importlib.abc
import importlib.machinery
import sys
import types
import typing as t

import dependency_injector.containers as containers
import dependency_injector.providers as providers
import dependency_injector.wiring as wiring
from dependency_injector.containers import Container
from dependency_injector.providers import Provider
from dependency_injector.wiring import as_float, as_int, ClassGetItemMeta, Closing, Provide, required, TypeModifier

P = t.ParamSpec("P")
TReturn = t.TypeVar("TReturn")


def inject(fn: t.Callable[P, TReturn]) -> t.Callable[P, TReturn]:  # noqa: E302
    reference_injections, reference_closing = wiring._fetch_reference_injections(fn)  # pyright: ignore [reportPrivateUsage] noqa: E501
    patched = wiring._get_patched(fn, reference_injections, reference_closing)  # pyright: ignore [reportPrivateUsage] noqa: E501

    # we need to update globals on route handlers to make sure pydantic
    # forward refs can be resolved
    if fn.__module__.startswith("socratic.web") and hasattr(fn, "__globals__"):
        wrapper = functools.wraps(fn, updated=("__globals__",))
        return wrapper(patched)
    return patched


TAs = t.TypeVar("TAs")
T = t.TypeVar("T")


class Manage(object, metaclass=ClassGetItemMeta):
    def __new__(cls, provider: Provider[T] | Container | str):
        return Closing[Provide[provider]]

    @classmethod
    def __class_getitem__(cls, item: Provider[T] | Container):
        return cls(item)


def as_(type_: t.Type[TAs]) -> TypeModifier:  # noqa: E302
    """Return custom type modifier."""
    # replace wiring.as_ because that one has typing issues
    return TypeModifier(type_)


class NotReady(object):
    _instance: t.ClassVar[NotReady | None] = None

    def __new__(cls) -> NotReady:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "<NotReady>"


class AutoLoader(object):
    """
    Rewrite of dependency_injector.wiring.AutoLoader to support optionally
    scoping autowiring to only members of named packages
    """

    containers: dict[str | None, list[Container]]
    _path_hook: t.Callable[[str], importlib.abc.PathEntryFinder] | None = None

    def __init__(self) -> None:
        self.containers = {}

    def register_containers(self, *containers: Container, packages: t.Sequence[str] | None) -> None:
        keys = packages or [None]
        for pkg in keys:
            self.containers.setdefault(pkg, []).extend(containers)

        if not self.installed:
            self.install()

    def unregister_containers(self, *containers: Container) -> None:
        for ls in self.containers.values():
            for container in containers:
                if container in ls:
                    ls.remove(container)

        if not self.containers:
            self.uninstall()

    def wire_module(self, module: str | types.ModuleType) -> None:
        # TODO: (2025-02-18) add logging here, if feasible
        for package, ls in self.containers.items():
            mname = module if isinstance(module, str) else module.__name__
            if package is None or mname.startswith(package):
                for container in ls:
                    container.wire(modules=[module])

    @property
    def installed(self) -> bool:
        return self._path_hook in sys.path_hooks

    def install(self) -> None:
        if self.installed:
            return

        loader = self

        class SourcelessFileLoader(importlib.machinery.SourcelessFileLoader):
            def exec_module(self, module: types.ModuleType):
                super().exec_module(module)
                loader.wire_module(module)

        class SourceFileLoader(importlib.machinery.SourceFileLoader):
            def exec_module(self, module: types.ModuleType):
                super().exec_module(module)
                loader.wire_module(module)

        class ExtensionFileLoader(importlib.machinery.ExtensionFileLoader): ...

        loader_details = [
            (ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
            (SourceFileLoader, importlib.machinery.SOURCE_SUFFIXES),
            (SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
        ]

        self._path_hook = importlib.machinery.FileFinder.path_hook(*loader_details)

        sys.path_hooks.insert(0, self._path_hook)
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()

    def uninstall(self) -> None:
        if self._path_hook is None or not self.installed:
            return

        sys.path_hooks.remove(self._path_hook)
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()


_loader = AutoLoader()


def register_loader_containers(*containers: Container, packages: t.Sequence[str] | None = None) -> None:
    """Register containers in auto-wiring module loader."""
    _loader.register_containers(*containers, packages=packages)
