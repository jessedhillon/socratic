"""Authentication utilities."""

__all__ = [
    "AuthContext",
    "AuthProvider",
    "AuthResult",
    "JWTManager",
    "TokenData",
    "get_current_user",
    "get_optional_user",
    "local",
    "require_educator",
    "require_learner",
    "require_role",
]

from . import local
from .jwt import JWTManager, TokenData
from .middleware import AuthContext, get_current_user, get_optional_user, require_educator, require_learner, \
    require_role
from .provider import AuthProvider, AuthResult
