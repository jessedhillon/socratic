import pydantic as p
from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import PydanticBaseSettingsSource

from socratic.model import BaseModel, DeploymentEnvironment

from .base import BaseSettings
from .logging import LoggingSettings
from .source import OverrideSettingsSource, YAMLCascadingSettingsSource
from .storage import StorageSettings
from .template import TemplateSettings
from .vendor import VendorSettings
from .web import WebSettings

SettingsField = p.Field(default=..., validate_default=True)


# NOTE: we use multiple inheritance so that we can get our preferred model_dump
#       alias=True behavior from BaseModel
class Settings(BaseSettings, BaseModel):  # pyright: ignore [reportIncompatibleVariableOverride]
    root: p.FileUrl
    env: DeploymentEnvironment
    override: tuple[str, ...]

    logging: LoggingSettings = SettingsField
    storage: StorageSettings = SettingsField
    template: TemplateSettings = SettingsField
    vendor: VendorSettings = SettingsField
    web: WebSettings = SettingsField

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[PydanticBaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:  # noqa: E501
        return init_settings, YAMLCascadingSettingsSource(settings_cls), OverrideSettingsSource(settings_cls)
