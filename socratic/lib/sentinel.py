from __future__ import annotations

import typing as t


class NotReady(object):
    _instance: t.ClassVar[NotReady | None] = None

    def __new__(cls) -> NotReady:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "<NotReady>"


class NotSet(object):
    _instance: t.ClassVar[NotSet | None] = None

    def __new__(cls) -> NotSet:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "<NotSet>"
