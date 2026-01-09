import os
import typing as t

import uvicorn

import socratic.lib.cli as click
import socratic.lib.debug as debug
from socratic.core import BootConfiguration, di
from socratic.core.config import LoggingSettings, WebSettings


class ServeConfig(t.TypedDict):
    host: str
    port: int


def _get_app_config(app_name: str, web_cf: WebSettings) -> tuple[str, ServeConfig]:
    """Get app module spec and serve config by convention.

    Apps follow the pattern:
    - Config: web_cf.{app_name}
    - Module: socratic.web.{app_name}:create_app
    """
    cf = getattr(web_cf, app_name, None)
    if cf is None:
        raise click.ClickException(f"unknown app '{app_name}' - not configured in web.yaml")

    spec = f"socratic.web.{app_name}:create_app"
    uvi_cf: ServeConfig = {"host": str(cf.backend.host), "port": cf.backend.port}
    return spec, uvi_cf


@click.group()
def web(): ...


@web.command(name="serve")
@click.argument("app_name")
@click.option("-w", "--workers", type=click.IntRange(min=1), default=1)
@di.inject
def serve(
    app_name: str,
    workers: int,
    boot_cf: BootConfiguration = di.Provide["_boot_config"],
    logging_cf: LoggingSettings = di.Provide["config.logging", di.as_(LoggingSettings)],  # noqa: B008
    web_cf: WebSettings = di.Provide["config.web", di.as_(WebSettings)],  # noqa: B008
):
    """Start a web app backend."""
    spec, uvi_cf = _get_app_config(app_name, web_cf)

    os.environ["__Socratic_BOOT"] = boot_cf.model_dump_json()
    uvicorn.run(spec, factory=True, workers=workers, log_config=logging_cf.model_dump(), **uvi_cf)


@web.command(name="develop")
@click.argument("app_name")
@click.option("-w", "--workers", type=click.IntRange(min=1), default=4)
@di.inject
def develop(
    app_name: str,
    workers: int,
    boot_cf: BootConfiguration = di.Provide["_boot_config"],
    logging_cf: LoggingSettings = di.Provide["config.logging", di.as_(LoggingSettings)],  # noqa: B008
    web_cf: WebSettings = di.Provide["config.web", di.as_(WebSettings)],  # noqa: B008
):
    """Start a web app backend with live-reload and remote debugging."""
    spec, uvi_cf = _get_app_config(app_name, web_cf)

    os.environ["__Socratic_BOOT"] = boot_cf.model_dump_json()
    with debug.remote_debugger():
        uvicorn.run(spec, factory=True, reload=True, workers=workers, log_config=logging_cf.model_dump(), **uvi_cf)
