"""View models for the Socratic web application."""

__all__ = [
    # Auth views
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "UserResponse",
    "TokenResponse",
    # Organization views
    "OrganizationResponse",
    "OrganizationCreateRequest",
    "InviteRequest",
    "InviteResponse",
    # Objective views
    "ObjectiveCreateRequest",
    "ObjectiveUpdateRequest",
    "ObjectiveResponse",
    "ObjectiveListResponse",
    "RubricCriterionRequest",
    "RubricCriterionResponse",
    "RubricCriterionCreateRequest",
    "GradeThresholdRequest",
    "GradeThresholdResponse",
    "FailureModeRequest",
    "FailureModeResponse",
    # Strand views
    "StrandCreateRequest",
    "StrandUpdateRequest",
    "StrandResponse",
    "StrandListResponse",
    "StrandWithObjectivesResponse",
    "ObjectiveInStrandRequest",
    "ObjectiveInStrandResponse",
    "ReorderObjectivesRequest",
    "ObjectiveDependencyRequest",
    "ObjectiveDependencyResponse",
]

from .auth import LoginRequest, LoginResponse, RegisterRequest, TokenResponse, UserResponse
from .objective import FailureModeRequest, FailureModeResponse, GradeThresholdRequest, GradeThresholdResponse, \
    ObjectiveCreateRequest, ObjectiveListResponse, ObjectiveResponse, ObjectiveUpdateRequest, \
    RubricCriterionCreateRequest, RubricCriterionRequest, RubricCriterionResponse
from .organization import InviteRequest, InviteResponse, OrganizationCreateRequest, OrganizationResponse
from .strand import ObjectiveDependencyRequest, ObjectiveDependencyResponse, ObjectiveInStrandRequest, \
    ObjectiveInStrandResponse, ReorderObjectivesRequest, StrandCreateRequest, StrandListResponse, StrandResponse, \
    StrandUpdateRequest, StrandWithObjectivesResponse
