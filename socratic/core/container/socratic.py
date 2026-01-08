from __future__ import annotations

import datetime
import os
import sys
import tempfile
import types
import typing as t
from pathlib import Path

import pydantic as p
import xdg_base_dirs as xdg
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Container, Object, Provider, Resource, Singleton

import socratic
from socratic.model import BaseModel, DeploymentEnvironment

from ..config import Secrets, Settings
from ..di import NotReady, register_loader_containers
from ..provider import LoggingProvider, TimestampProvider
from .auth import AuthContainer
from .storage import StorageContainer
from .template import TemplateContainer
from .vendor import VendorContainer


def provide_xdg_runtime() -> t.Generator[Path]:
    rtp = xdg.xdg_runtime_dir()
    if rtp:
        yield rtp
    else:
        rtp = Path(tempfile.mkdtemp())
        yield rtp
        os.rmdir(rtp)


def provide_xdg_state() -> Path:
    stp = xdg.xdg_state_home() / "socratic"
    if stp.exists() and stp.is_dir():
        return stp
    stp.mkdir(exist_ok=True)
    return stp


class BootConfiguration(BaseModel):
    debug: bool
    env: DeploymentEnvironment
    config_root: p.AnyUrl
    secrets_path: p.AnyUrl | None = None
    override: tuple[str, ...]


class SocraticContainer(DeclarativeContainer):
    config: Configuration = Configuration()
    secrets: Configuration = Configuration()

    debug: Provider[bool] = Singleton(bool)
    env: Provider[DeploymentEnvironment] = Singleton(DeploymentEnvironment)
    root: Object[NotReady | Path] = Object(NotReady())
    runtime_path: Provider[Path] = Resource(provide_xdg_runtime)
    state_path: Provider[Path] = Resource(provide_xdg_state)

    logging: Provider[LoggingProvider] = Resource(LoggingProvider, config=config.logging, debug=debug)
    storage: Provider[StorageContainer] = Container(
        StorageContainer, config=config.storage, secrets=secrets, debug=debug, logging=logging, root=root
    )
    template: Provider[TemplateContainer] = Container(TemplateContainer, config=config.template)
    vendor: Provider[VendorContainer] = Container(VendorContainer, config=config.vendor, secrets=secrets)

    # Auth container - config comes from web.socratic.auth, session from storage
    auth: Provider[AuthContainer] = Container(
        AuthContainer,
        config=config.web.socratic.auth,
        secrets=secrets.auth,
        session=storage.provided.persistent.session,
    )

    utcnow: Provider[TimestampProvider] = Object(lambda: datetime.datetime.now(datetime.UTC))

    _boot_config: Provider[BootConfiguration | NotReady] = Object(NotReady())

    @staticmethod
    def boot(
        ct: SocraticContainer,
        /,
        debug: bool,
        env: DeploymentEnvironment,
        config_root: p.FileUrl,
        secrets_path: p.AnyUrl | None = None,
        override: tuple[str, ...] | None = None,
        wiring: tuple[str | types.ModuleType, ...] | None = None,
    ):
        if config_root.scheme != "file":
            raise ValueError(f"unsupported scheme for config root: {config_root.scheme}")
        ps = Settings(env=env, root=config_root, override=override or ())
        ct.config.from_pydantic(ps)
        ct.wire(
            # TODO: (2025-02-18) review this list to see if this is truly the
            #                    minimal base wiring set
            packages=[
                "socratic",
                "socratic.lib",
            ]
        )
        if wiring:
            ct.wire(modules=wiring)
        if imported := [mod for name, mod in sys.modules.items() if name.startswith("socratic.")]:
            ct.wire(modules=imported)
        register_loader_containers(ct, packages=["socratic"])

        logger = ct.logging().get_logger()

        for ov in ps.override:
            k, v = ov.split("=", 1)
            logger.info(
                "overriding configuration parameter",
                extra={
                    "key": k,
                    "value": v,
                },
            )

        ct.debug.override(debug)
        ct.env.override(env)
        ct.root.override(Path(os.path.dirname(socratic.__file__)).parent)
        if debug:
            ct.logging().capture_warnings(True)

        if secrets_path is None and env is not DeploymentEnvironment.Local:
            secrets_path = p.AnyUrl(f"aws:///{env.value}/secrets")
            secrets = Secrets(env=env, root=secrets_path or config_root)
        else:
            secrets = Secrets(env=env, root=secrets_path or config_root)
        ct.secrets.from_pydantic(secrets)

        logger.debug(
            "configuration finished",
            extra={
                "config": str(config_root),
            },
        )
        ct._boot_config.override(
            BootConfiguration(
                debug=debug, env=env, config_root=config_root, secrets_path=secrets_path, override=override or ()
            )
        )
