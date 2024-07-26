import typing as t
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.parse.parser import Parser
from kye.type.type_builder import TypeBuilder
from kye.vm.loader import Loader
from kye.errors.base_reporter import ErrorReporter
from kye.errors.compilation_errors import CompilationErrorReporter
from kye.errors.validation_errors import ValidationErrorReporter
from kye.type.compiler import compile
from kye.compiled import Compiled
from kye.vm.vm import VM

class Kye:
    reporter: ErrorReporter
    type_builder: TypeBuilder
    vm: VM
    loader: t.Optional[Loader]
    compiled: t.Optional[Compiled]

    def __init__(self):
        self.type_builder = TypeBuilder()
        self.loader = None
        self.compiled = None
    
    def parse_definitions(self, source: str) -> t.Optional[ast.Script]:
        """ Parse definitions from source code """
        self.reporter = CompilationErrorReporter(source)
        parser = Parser(self.reporter)
        tree = parser.parse_definitions(source)
        if self.reporter.had_error:
            return None
        return tree

    # def parse_expression(self, source: str) -> t.Optional[ast.Expr]:
    #     """ Parse an expression from source code """
    #     self.reporter = ErrorReporter(source)
    #     parser = Parser(self.reporter)
    #     tree = parser.parse_expression(source)
    #     if self.reporter.had_error:
    #         return None
    #     return tree

    def build_types(self, tree: t.Optional[ast.Node]) -> t.Optional[typ.Types]:
        """ Build types from the AST """
        if tree is None:
            return None
        self.type_builder.reporter = t.cast(CompilationErrorReporter, self.reporter)
        self.type_builder.visit(tree)
        if self.reporter.had_error:
            return None
        return self.type_builder.types
    
    def read(self, filepath: str) -> bool:
        if filepath.split('.')[-1] in ('json','yaml','yml'):
            return self.read_compiled(filepath)
        return self.read_script(filepath)
    
    def read_script(self, filepath: str) -> bool:
        with open(filepath, "r") as file:
            source = file.read()
        return self.compile(source)

    def compile(self, source: str) -> bool:
        tree = self.parse_definitions(source)
        types = self.build_types(tree)
        if types is None:
            return False
        compiled = compile(types)
        return self.load_compiled(compiled)

    def load_compiled(self, compiled: Compiled) -> bool:
        self.compiled = compiled
        self.reporter = ValidationErrorReporter()
        self.loader = Loader(self.compiled, self.reporter)
        return not self.reporter.had_error

    def read_compiled(self, filepath: str) -> bool:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(path)
        text = path.read_text()
        if path.suffix in ('.yaml', '.yml'):
            import yaml
            raw = yaml.safe_load(text)
        elif path.suffix == '.json':
            import json
            raw = json.loads(text)
        else:
            raise ValueError(f'Unsupported file extension: {path.suffix}')
        compiled = Compiled.from_dict(raw)
        return self.load_compiled(compiled)
    
    def write_compiled(self, filepath: str):
        assert self.compiled is not None
        raw = self.compiled.to_dict()
        path = Path(filepath)
        text = None
        if path.suffix in ('.yaml', '.yml'):
            import yaml
            text = yaml.dump(raw, sort_keys=False)
        elif path.suffix == '.json':
            import json
            text = json.dumps(raw, sort_keys=False, indent=2)
        else:
            raise ValueError(f'Unsupported file extension: {path.suffix}')
        path.write_text(text)
    
    def load_file(self, source_name: str, filepath: str):
        assert self.loader is not None
        file = Path(filepath)
        if file.suffix == '.csv':
            table = pd.read_csv(file)
        elif file.suffix == '.json':
            table = pd.read_json(file)
        elif file.suffix == '.jsonl':
            table = pd.read_json(file, lines=True)
        else:
            raise ValueError(f"Unknown file type {file.suffix}")
        self.load_df(source_name, table)

    def load_df(self, source_name: str, table: pd.DataFrame):
        assert self.loader is not None
        self.loader.load(source_name, table)
    
    # def validate_model(self, source_name: str):
    #     assert self.vm is not None
    #     self.vm.validate(source_name)
    
    # def eval_expression(self, source: str) -> t.Any:
    #     assert self.vm is not None
    #     tree = self.parse_expression(source)
    #     self.build_types(tree)
    #     self.vm.reporter = self.reporter
    #     if tree is None:
    #         return None
    #     try:
    #         return self.vm.visit(tree)
    #     except KyeRuntimeError as error:
    #         self.reporter.runtime_error(error)