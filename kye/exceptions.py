from __future__ import annotations
import typing as t

if t.TYPE_CHECKING:
    from kye.parse.expressions import Token


class KyeRuntimeError(RuntimeError):
    token: Token

    def __init__(self, token: Token, message: str):
        super().__init__(message)
        self.token = token

class ParserError(Exception):
    pass
