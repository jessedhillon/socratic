"""Authentication utilities."""

__all__ = [
    "AuthContext",
    "AuthProvider",
    "AuthResult",
    "JWTManager",
    "LocalAuthProvider",
    "TokenData",
    "get_current_user",
    "get_optional_user",
    "require_educator",
    "require_learner",
    "require_role",
]

from .jwt import JWTManager, TokenData
from .local import LocalAuthProvider
from .middleware import AuthContext, get_current_user, get_optional_user, require_educator, require_learner, \
    require_role
from .provider import AuthProvider, AuthResult
