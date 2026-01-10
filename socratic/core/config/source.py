import functools
import getpass
import typing as t
from pathlib import Path

import pydantic as p
import yaml
from ansible.parsing.vault import VaultLib, VaultSecret
from keyctl import Key as keyctl
from keyctl import KeyNotExistError
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings.sources import SettingsError

import socratic.lib.util as util
from socratic.model import DeploymentEnvironment


class CurrentState(t.TypedDict, total=False):
    root: t.Required[p.AnyUrl]
    env: t.Required[DeploymentEnvironment]


class SettingsCurrentState(CurrentState, total=False):
    override: t.Required[tuple[str, ...]]


class SettingsSource(PydanticBaseSettingsSource):
    def __call__(self) -> dict[str, t.Any]:
        # we expect init kwargs to have config root and env in them
        data: dict[str, t.Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            try:
                field_value, field_key, value_is_complex = self.get_field_value(field, field_name)
                field_value = self.prepare_field_value(field_name, field, field_value, value_is_complex)
            except KeyError:
                continue
            except ValueError as e:
                raise SettingsError(f"error parsing value for field {field_name!r} from source {self!r}") from e
            except Exception as e:
                raise SettingsError(f"error getting value for field {field_name!r} from source {self!r}") from e

            data[field_key] = field_value
        return data


class OverrideSettingsSource(SettingsSource):
    def __call__(self) -> dict[str, t.Any]:
        rs = super().__call__()
        return rs

    @functools.cached_property
    def parsed_options(self) -> dict[str, t.Any]:
        current_state = t.cast(SettingsCurrentState, self.current_state)
        override = current_state["override"]
        od: dict[str, t.Any] = {}
        for o in override:
            k, v = [s.strip() for s in o.split("=", 1)]

            target = od
            path = k.split(".")
            for key in path[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            key = path[-1]
            target[key] = yaml.safe_load(v)
        return od

    def get_field_value(self, field: p.fields.FieldInfo, field_name: str) -> t.Any:
        current_state = t.cast(SettingsCurrentState, self.current_state)
        skip_keys = {"env", "root", "override"}
        val = current_state.get(field_name)
        if field_name in self.parsed_options and field_name not in skip_keys:
            if isinstance(val, dict):
                merged = util.deep_update(t.cast(dict[t.Any, t.Any], val), self.parsed_options[field_name])
                return merged, field_name, True
            return self.parsed_options[field_name], field_name, False
        return val, field_name, False

    def prepare_field_value(
        self, field_name: str, field: p.fields.FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        return value


class YAMLCascadingSettingsSource(SettingsSource):
    @functools.cached_property
    def load_paths(self) -> list[Path]:
        current_state = t.cast(SettingsCurrentState, self.current_state)
        root = current_state["root"]
        assert root.scheme == "file" and root.path is not None, "root is not a legible location of YAML files"
        env = current_state["env"]
        paths = [Path(root.path)]
        if env is not DeploymentEnvironment.Local:
            # we don't have a special directory for local/ that's just root
            paths.append(Path(root.path) / "env.d" / env.value)
        return paths

    def get_field_value(self, field: p.fields.FieldInfo, field_name: str) -> tuple[t.Any, str, bool]:
        yamls: list[str] = []
        for path in self.load_paths:
            fn = path / f"{field_name}.yaml"
            if fn.exists():
                yamls.append(fn.read_text(encoding="utf8"))
        if not yamls:
            raise KeyError(field_name)
        return yamls, field_name, True

    def prepare_field_value(
        self, field_name: str, field: p.fields.FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        if not value_is_complex:
            return super().prepare_field_value(field_name, field, value, value_is_complex)

        # for complex values, we expect to be given a list[str] representing
        # the yamls encountered along the load_paths
        if not isinstance(value, list):
            raise ValueError(field_name)
        yamls = t.cast(list[str], value)
        return yaml.safe_load(yamls[-1])


class AnsibleVaultSecretsSource(SettingsSource):
    @functools.cached_property
    def load_path(self) -> Path:
        current_state = t.cast(CurrentState, self.current_state)
        root = current_state["root"]
        assert root.scheme == "file" and root.path is not None, "root is not a legible location of YAML files"
        rootp = Path(root.path)
        env = current_state["env"]
        if env is not DeploymentEnvironment.Local:
            # we don't have a special directory for local/ that's just the root
            return rootp / "env.d" / env.value
        return rootp

    @functools.cached_property
    def secrets(self) -> dict[str, t.Any]:
        current_state = t.cast(CurrentState, self.current_state)
        env = current_state["env"]
        fn = "secrets.vault.yaml"
        vp = self.load_path / fn

        # Early return if no vault file - avoid prompting for password
        if not vp.exists():
            return {}

        key_name = f"{env.value}:{fn}"
        try:
            store_key: bool = False
            k = keyctl.search(key_name)
            key = k.data
        except KeyNotExistError:
            # don't save the key until/unless it successfully unlocks the vault
            key = getpass.getpass(f"provide vault key ({key_name})󰌾 ")
            store_key = True

        # INFO: None is the vault-id -- if we start using a vault ID, we need to specify it here
        vault = VaultLib(secrets=[(None, VaultSecret(key.encode()))])
        with vp.open() as f:
            content = vault.decrypt(f.read())
            if store_key:
                keyctl.add(key_name, key)
            return yaml.safe_load(content)

    def get_field_value(self, field: p.fields.FieldInfo, field_name: str) -> tuple[t.Any, str, bool]:
        skip_keys = {"env", "root", "override"}
        # Check skip_keys before accessing self.secrets to avoid circular dependency
        # (self.secrets needs current_state["root"] to compute load_path)
        if field_name in skip_keys:
            raise KeyError(field_name)
        val = self.secrets.get(field_name)
        if field_name in self.secrets:
            if isinstance(val, dict):
                merged = util.deep_update(t.cast(dict[t.Any, t.Any], val), self.secrets[field_name])
                return merged, field_name, True
            return self.secrets[field_name], field_name, False
        return val, field_name, False

    def prepare_field_value(
        self, field_name: str, field: p.fields.FieldInfo, value: t.Any, value_is_complex: bool
    ) -> t.Any:
        if not value_is_complex:
            return super().prepare_field_value(field_name, field, value, value_is_complex)
        return value
