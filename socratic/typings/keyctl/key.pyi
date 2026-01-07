import typing as t

import annotated_types as at

SystemKeyring = t.Literal['@u', '@t', '@p', '@s', '@us', '@g', '@a']
NamedKeyring = t.Annotated[str, at.Predicate(lambda s: s.startswith('%:'))]
Keyring = SystemKeyring | NamedKeyring

class Key(object):
    data: str

    @classmethod
    def search(cls, name: str, keyring: Keyring | None = None, keytype: str | None = None) -> Key: ...

    @classmethod
    def add(cls, name: str, data: str | bytes, keyring: Keyring | None = None, keytype: str | None = None) -> Key: ...
