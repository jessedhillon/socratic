"""View models for the Socratic web application."""

__all__ = [
    # Auth views
    "LoginRequest",
    "LoginOkResponse",
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
    "ProficiencyLevelRequest",
    "ProficiencyLevelResponse",
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
    # Assignment views
    "AssignmentCreateRequest",
    "AssignmentUpdateRequest",
    "AssignmentResponse",
    "AssignmentListResponse",
    "AssignmentWithAttemptsResponse",
    "BulkAssignmentCreateRequest",
    "AttemptResponse",
    "LearnerResponse",
    "LearnerListResponse",
    "LearnerAssignmentSummary",
    "LearnerDashboardResponse",
]

from .assignment import AssignmentCreateRequest, AssignmentListResponse, AssignmentResponse, AssignmentUpdateRequest, \
    AssignmentWithAttemptsResponse, AttemptResponse, BulkAssignmentCreateRequest, LearnerAssignmentSummary, \
    LearnerDashboardResponse, LearnerListResponse, LearnerResponse
from .auth import LoginOkResponse, LoginRequest, RegisterRequest, TokenResponse, UserResponse
from .objective import ObjectiveCreateRequest, ObjectiveListResponse, ObjectiveResponse, ObjectiveUpdateRequest, \
    ProficiencyLevelRequest, ProficiencyLevelResponse, RubricCriterionCreateRequest, RubricCriterionRequest, \
    RubricCriterionResponse
from .organization import InviteRequest, InviteResponse, OrganizationCreateRequest, OrganizationResponse
from .strand import ObjectiveDependencyRequest, ObjectiveDependencyResponse, ObjectiveInStrandRequest, \
    ObjectiveInStrandResponse, ReorderObjectivesRequest, StrandCreateRequest, StrandListResponse, StrandResponse, \
    StrandUpdateRequest, StrandWithObjectivesResponse
