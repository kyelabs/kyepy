from __future__ import annotations
from typing import Optional

# TODO: All of this fancy path parsing could probably lead to security vulnerabilities
# if edge names are not properly sanitized. Should probably remove it from the released
# version, and just keep it for debugging for now.
def normalize_path(key: str) -> tuple[str]:
    assert key != '', f'Environment path shouldn\'t be empty'
    assert '..' not in key, f'Environment path shouldn\'t have a double period "{key}"'
    return key.split('.')

class Environment:
    local: dict[str, ChildEnvironment]

    def __init__(self):
        self.local = {}
    
    @property
    def path(self) -> tuple[str]:
        return tuple()

    @property
    def global_name(self) -> str:
        return '.'.join(self.path)

    def _resolve(self, key: str) -> Optional[Environment]:
        """ Travel up the Environment hierarchy,
        returning the environment that contains this key """
        assert '.' not in key
        if key in self.local or key == '':
            return self
        return None
    
    def _descend(self, path: tuple[str]) -> Optional[Environment]:
        """ Travel down the Environment hierarchy,
        returning the environment at the end of this path """
        if len(path) == 0:
            return self
        if path[0] == '':
            return self._descend(path[1:])
        if path[0] in self.local:
            return self.local[path[0]]._descend(path[1:])
        return None

    def _resolve_path(self, path: tuple[str]) -> Optional[Environment]:
        """ Search up the Environment hierarchy for the first key in the path,
        then travel down the path from there """
        return self._descend(path)

    def __getitem__(self, key: str) -> ChildEnvironment:
        env = self._resolve_path(normalize_path(key))
        if env is None:
            raise KeyError(f'"{key}" not defined')
        return env
    
    def __contains__(self, key) -> bool:
        return self._resolve_path(normalize_path(key)) is not None

    def __repr__(self):
        return self.global_name + '{' + ','.join(self.local.keys()) + '}'


class ChildEnvironment(Environment):
    name: str
    parent: Environment

    def __init__(self, name: str, parent: Environment):
        super().__init__()
        assert type(name) is str
        assert '.' not in name
        assert isinstance(parent, Environment)
        self.name = name
        self.parent = parent
        assert self.name not in self.parent.local
        self.parent.local[self.name] = self
    
    @property
    def path(self) -> tuple[str]:
        return (*self.parent.path, self.name)
    
    def _resolve(self, key: str):
        """ Travel up the Environment hierarchy,
        returning the environment that contains this key """
        return super()._resolve(key) or self.parent._resolve(key)

    def _resolve_path(self, path: tuple[str]) -> ChildEnvironment:
        """ Search up the Environment hierarchy for the first key in the path,
        then travel down the path from there """
        env = self._resolve(path[0]) if len(path) > 0 else self
        return env._descend(path)
