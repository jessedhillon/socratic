import enum


class DeploymentEnvironment(enum.Enum):
    Production = "production"
    Development = "development"
    Staging = "staging"
    Sandbox = "sandbox"
    Test = "test"
    Local = "local"
