import socratic.lib.cli as click
from socratic.core import di
from socratic.model import DeploymentEnvironment


@click.group("example")
def example(): ...


@example.command()
@di.inject
def hello(env: DeploymentEnvironment = di.Provide["env"]):
    click.echo(f"hello from {env.name}")
