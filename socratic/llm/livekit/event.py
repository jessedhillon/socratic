"""Pydantic models for LiveKit data channel events."""

from __future__ import annotations

import typing as t

import pydantic as p

from socratic.model import AttemptID


class AssessmentCompleteEvent(p.BaseModel):
    type: t.Literal["assessment.complete"] = "assessment.complete"
    attempt_id: AttemptID


class AssessmentErrorEvent(p.BaseModel):
    type: t.Literal["assessment.error"] = "assessment.error"
    attempt_id: AttemptID
    message: str
    fatal: bool
