from __future__ import annotations
import typing as t
from dataclasses import dataclass

import pandas as pd

import kye.exceptions as exc

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

@dataclass(frozen=True, kw_only=True)
class Error:
    msg: t.Optional[str] = None
    
    def get_message(self):
        return self.msg
    
    def highlight_source_code(self, source: str) -> t.Optional[str]:
        return None
    
    def highlight_df(self, df: pd.DataFrame) -> t.Optional[pd.DataFrame]:
        return None

@dataclass(frozen=True, kw_only=True)
class SourceCodeError(Error):
    start: int
    end: int
    
    def highlight_source_code(self, source: str) -> str:
        return highlight(source, self.start, self.end)

@dataclass(frozen=True, kw_only=True)
class ScannerError(SourceCodeError):
    pass

@dataclass(frozen=True, kw_only=True)
class ParserError(SourceCodeError):
    pass

@dataclass(frozen=True, kw_only=True)
class ValidationError(Error):
    loc: t.Optional[str]
    
    def highlight_source_code(self, source: str) -> t.Optional[str]:
        if not self.loc:
            return None
        line, col = list(map(int,self.loc.split(':')))
        return f'   on line {line}'
        

@dataclass(frozen=True, kw_only=True)
class ColumnTypeError(ValidationError):
    model: str
    edge: str
    expected: str
    
    def get_message(self):
        return f"Expected {self.model}.{self.edge} to be of type '{self.expected}'"
    
    def highlight_df(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[[self.edge]]

@dataclass(frozen=True, kw_only=True)
class CardinalityError(ValidationError):
    model: str
    edge: str
    rows: t.List[int]
    cardinality: str
    
    def get_message(self):
        if self.cardinality == 'more':
            return f"Expected {self.model}.{self.edge} to not be null"
        if self.cardinality == 'maybe':
            return f"Expected {self.model}.{self.edge} to not have more than one value"
        if self.cardinality == 'one':
            return f"Expected {self.model}.{self.edge} to have a single non-null value"
        raise ValueError(f"Invalid cardinality: {self.cardinality}")
    
    def highlight_df(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.loc[self.rows, [self.edge]]

@dataclass(frozen=True, kw_only=True)
class AssertionError(ValidationError):
    model: str
    edges: t.List[str]
    rows: t.List[int]
    
    def get_message(self):
        return f"Assertion failed {self.msg or ''}"
    
    def highlight_df(self, df: pd.DataFrame) -> pd.DataFrame | None:
        return df.loc[self.rows, self.edges]

@dataclass(frozen=True, kw_only=True)
class MissingIndexError(ValidationError):
    model: str
    edges: t.List[str]
    
    def get_message(self):
        return f"{self.model} is missing index columns: {','.join(self.edges)}"

class ErrorReporter:
    errors: t.List[Error]
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
        self.errors.append(ScannerError(
            start=len(self.source) - 1,
            end=len(self.source),
            msg=message,
        ))

    def unexpected_character_error(self, pos: int):
        # if self.had_error:
        #     last_error = self.errors[-1]
        #     if last_error[1] == pos - 1 and last_error[2] == message:
        #         self.errors[-1] = (last_error[0], pos, message)
        #         return
        self.errors.append(ScannerError(
            start=pos,
            end=pos,
            msg="Unexpected character",
        ))
    
    def unterminated_expression_error(self, token: Token, message: str):
        self.errors.append(ParserError(
            start=token.loc.start,
            end=token.loc.end,
            msg=message,
        ))
        return exc.ParserError()

    def parser_error(self, token: Token, message):
        self.errors.append(ParserError(
            start=token.loc.start,
            end=token.loc.end,
            msg=message,
        ))
        return exc.ParserError()

    def column_type_error(self, edge: compiled.Edge):
        assert self.loading is not None
        assert edge.name in self.loading[1].columns
        self.errors.append(ColumnTypeError(
            model=edge.model,
            edge=edge.name,
            loc=edge.loc,
            expected=edge.type,
        ))
    
    def cardinality_error(self, edge: compiled.Edge, rows: t.List[int]):
        assert self.loading is not None
        self.errors.append(CardinalityError(
            model=edge.model,
            edge=edge.name,
            loc=edge.loc,
            rows=rows,
            cardinality=edge.cardinality,
        ))
    
    def assertion_error(self, assertion: compiled.Assertion, rows: t.List[int]):
        assert self.loading is not None
        self.errors.append(AssertionError(
            model=assertion.model,
            edges=assertion.edges,
            loc=assertion.loc,
            rows=rows,
            msg=assertion.msg,
        ))
    
    def missing_index_column_error(self, edge: compiled.Edge):
        assert self.loading is not None
        self.errors.append(MissingIndexError(
            model=edge.model,
            edges=[edge.name],
            loc=edge.loc,
        ))
    
    def report(self):
        for err in self.errors:
            print(f"Error: {err.get_message()}")
            if self.source is not None and len(self.source) > 0:
                highlighted = err.highlight_source_code(self.source)
                if highlighted is not None:
                    print(highlighted)
            if self.loading is not None:
                model_name, df = self.loading
                assert isinstance(df.index, pd.RangeIndex)
                df.index.name = model_name
                highlighted = err.highlight_df(df)
                if highlighted is not None:
                    print(highlighted.head(5).reset_index().to_string(index=False))