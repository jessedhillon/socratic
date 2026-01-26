from __future__ import annotations

import pydantic as p
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from socratic.model import BaseModel, DeploymentEnvironment

from .base import BaseSecrets
from .source import AnsibleVaultSecretsSource


class PostgresqlSecrets(BaseSecrets):
    username: p.Secret[str] | None = None
    password: p.Secret[str] | None = None


class AuthSecrets(BaseSecrets):
    """Authentication secrets."""

    jwt: p.Secret[str]


class OpenAISecrets(BaseSecrets):
    """OpenAI API secrets."""

    secret_key: p.Secret[str] | None = None


class GoogleServiceAccountSecrets(BaseSecrets):
    private_key: p.Secret[str]


class GoogleSecrets(BaseSecrets):
    service_account: GoogleServiceAccountSecrets


class LiveKitSecrets(BaseSecrets):
    """LiveKit API secrets."""

    api_key: p.Secret[str]
    api_secret: p.Secret[str]
    wss_url: p.Secret[p.WebsocketUrl]


class Secrets(BaseSecrets, BaseModel):  # pyright: ignore [reportIncompatibleVariableOverride]
    root: p.AnyUrl
    env: DeploymentEnvironment

    auth: AuthSecrets | None = None
    openai: OpenAISecrets | None = None
    livekit: LiveKitSecrets | None = None
    # google: GoogleSecrets = p.Field(default=..., validate_default=True)
    # postgresql: PostgresqlSecrets = p.Field(default_factory=PostgresqlSecrets, validate_default=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, AnsibleVaultSecretsSource(settings_cls)
