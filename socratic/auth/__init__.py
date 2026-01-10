"""Authentication utilities."""

__all__ = [
    "AuthContext",
    "AuthProvider",
    "AuthResult",
    "TokenData",
    "get_current_user",
    "get_optional_user",
    "jwt",
    "local",
    "require_educator",
    "require_learner",
    "require_role",
]

from . import jwt, local
from .jwt import TokenData
from .middleware import AuthContext, get_current_user, get_optional_user, require_educator, require_learner, \
    require_role
from .provider import AuthProvider, AuthResult
