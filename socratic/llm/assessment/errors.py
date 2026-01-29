"""Exceptions for assessment operations."""


class AssessmentError(Exception):
    """Error during an assessment operation."""

    pass


class SessionNotFoundError(AssessmentError):
    """Assessment session state could not be found."""

    pass
