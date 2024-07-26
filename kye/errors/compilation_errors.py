from __future__ import annotations
import typing as t
from dataclasses import dataclass

import kye.errors.exceptions as exc
from kye.errors.base_reporter import ErrorReporter

if t.TYPE_CHECKING:
    from kye.parse.expressions import Token
    import kye.compiled as compiled

def get_line_pos(source: str, pos: int) -> t.Tuple[int, int, int]:
    line_num = source[:pos].count("\n") + 1
    line_start = source.rfind("\n", 0, pos) + 1
    line_end = source.find("\n", line_start)
    if line_end == -1:
        line_end = len(source)
    return line_num, line_start, line_end

def highlight(source: str, start: int, end: int) -> str:
    line, line_start, line_end = get_line_pos(source, start)
    prefix = f" {line} | "
    err_len = max(min(end - start, line_end - start), 1)
    return (
        prefix + source[line_start:line_end] + "\n" +
        " " * len(prefix) + " " * (start - line_start) + "^" * err_len
    )

@dataclass
class Error:
    start: int
    end: int
    msg: str

class CompilationErrorReporter(ErrorReporter):
    source: str
    errors: t.List[Error]

    def __init__(self, source: str):
        self.errors = []
        self.source = source
    
    @property
    def had_error(self):
        return len(self.errors) > 0

    def _append_error(self, start: int, end: int, msg: str):
        if self.had_error:
            last_error = self.errors[-1]
            if last_error.end >= start - 1 and last_error.msg == msg:
                self.errors[-1].end = end
                return
        self.errors.append(Error(start, end, msg))

    def unterminated_token_error(self, message: str):
        self._append_error(len(self.source) - 1, len(self.source), message)

    def unexpected_character_error(self, pos: int):
        self._append_error(pos, pos, "Unexpected character")

    def parser_error(self, token: Token, message: str):
        self._append_error(token.loc.start, token.loc.end, message)
        return exc.ParserError()
    
    def report(self):
        for err in self.errors:
            print(f"Error: {err.msg}")
            print(highlight(self.source, err.start, err.end))