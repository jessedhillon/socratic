"""Flights web application for prompt experimentation tracking."""

import os
import typing as t
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from socratic.core import BootConfiguration, di, SocraticContainer
from socratic.core.config import FlightsWebSettings
from socratic.model import DeploymentEnvironment

from .route import router


@di.inject
def _create_app(
    config: FlightsWebSettings = di.Provide["config.web.flights", di.as_(FlightsWebSettings)],
    env: DeploymentEnvironment = di.Provide["env"],
    root_path: Path = di.Provide["root"],
) -> FastAPI:
    app = FastAPI(
        title="Flights",
        description="Prompt experimentation tracking service",
    )
    if env is DeploymentEnvironment.Local:
        if config.frontend is not None:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=[
                    f"http://{config.frontend.host}:{config.frontend.port}",
                    f"http://localhost:{config.frontend.port}",
                ],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        else:
            # Allow all origins in local mode without frontend
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
    app.include_router(router)
    return app


def create_app() -> FastAPI:
    boot_vars = os.getenv("__Socratic_BOOT")
    if boot_vars:
        boot_cf = BootConfiguration.model_validate_json(boot_vars)
        ct = SocraticContainer()
        SocraticContainer.boot(ct, **dict(boot_cf))
        ct.wire(modules=["socratic.web.flights.main"])
        return _create_app(
            config=FlightsWebSettings(**ct.config.web.flights()),
            env=boot_cf.env,
            root_path=t.cast(Path, ct.root()),
        )
    return _create_app()
