from __future__ import annotations
import typing as t

import pandas as pd

if t.TYPE_CHECKING:
    from kye.parse.expressions import Token

class KyeRuntimeError(RuntimeError):
    token: Token

    def __init__(self, token: Token, message: str):
        super().__init__(message)
        self.token = token

class ParserError(Exception):
    pass

class ErrorReporter:
    error_type: t.Optional[str]
    loading: t.Optional[t.Tuple[str, pd.DataFrame]]

    def __init__(self, source: str):
        self.errors = []
        self.error_type = None
        self.source = source
        self.loading = None
    
    @property
    def had_error(self):
        return len(self.errors) > 0

    def unterminated_token_error(self, message: str):
        self.errors.append((len(self.source) - 1, len(self.source), message, []))
        self.error_type = "unterminated"

    def unexpected_character_error(self, pos: int):
        message = "Unexpected character."
        # if self.had_error:
        #     last_error = self.errors[-1]
        #     if last_error[1] == pos - 1 and last_error[2] == message:
        #         self.errors[-1] = (last_error[0], pos, message)
        #         return
        self.error_type = "scanner"
        self.errors.append((pos, pos, message, []))
    
    def unterminated_expression_error(self, token: Token, message: str):
        self.errors.append((token.start, token.end, message, []))
        self.error_type = "unterminated"
        return ParserError()

    def parser_error(self, token: Token, message):
        self.errors.append((token.start, token.end, message, []))
        self.error_type = "parser"
        return ParserError()

    def loading_edge_error(self, loc: t.Optional[str], edge: str, message):
        assert self.loading is not None
        start,end = list(map(int,loc.split(':'))) if loc else [-1,-1]
        self.errors.append((start, end, message, [ edge ]))
        self.error_type = "loader"
    
    def report(self):
        for start, end, message, edges in self.errors:
            print(f"Error: {message}")
            if start != -1:
                line, line_start, line_end = self.get_line_pos(start)
                prefix = f" {line} | "
                print(prefix + self.source[line_start:line_end])
                err_len = max(min(end - start, line_end - start), 1)
                print(" " * len(prefix) + " " * (start - line_start) + "^" * err_len)
            if len(edges) > 0:
                if self.loading:
                    model_name, df = self.loading
                    assert isinstance(df.index, pd.RangeIndex)
                    df.index.name = model_name
                    print(df[edges].head(5).reset_index().to_string(index=False))
    
    def get_line_pos(self, pos: int) -> t.Tuple[int, int, int]:
        line_num = self.source[:pos].count("\n") + 1
        line_start = self.source.rfind("\n", 0, pos) + 1
        line_end = self.source.find("\n", line_start)
        if line_end == -1:
            line_end = len(self.source)
        return line_num, line_start, line_end