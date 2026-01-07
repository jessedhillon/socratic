import pathlib

import jinja2
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Provider, ThreadSafeSingleton

from socratic.core import di


class TemplateContainer(DeclarativeContainer):
    @staticmethod
    @di.inject
    def provide_jinja_env(template_path: str, root_path: pathlib.Path = di.Provide["root"]) -> jinja2.Environment:
        import jinja2

        import socratic.lib.json

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(root_path.joinpath(template_path)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )
        env.policies.update({
            "json.dumps_function": socratic.lib.json.dumps,
        })
        return env

    config: Configuration = Configuration(strict=True)
    example: Provider[jinja2.Environment] = ThreadSafeSingleton(provide_jinja_env, config.example_path)
