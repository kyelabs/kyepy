import typing as t
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.parse.parser import Parser
from kye.type.type_builder import TypeBuilder
from kye.vm.loader import Loader
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.compiler import Compiled, compile, write_compiled
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
        self.reporter = ErrorReporter(source)
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
        self.type_builder.reporter = self.reporter
        self.type_builder.visit(tree)
        if self.reporter.had_error:
            return None
        return self.type_builder.types
    
    def compile(self, source: str) -> bool:
        tree = self.parse_definitions(source)
        types = self.build_types(tree)
        if types is None:
            return False
        self.compiled = compile(types)
        self.loader = Loader(self.compiled, self.reporter)
        self.vm = VM(self.loader)
        self.vm.reporter = self.reporter
        return not self.reporter.had_error
    
    def write_compiled(self, filepath: str):
        assert self.compiled is not None
        write_compiled(self.compiled, filepath)

    def load(self, source_name: str, table: pd.DataFrame):
        assert self.loader is not None
        self.loader.load(source_name, table)
    
    def read(self, source_name: str, filepath: str):
        assert self.loader is not None
        self.loader.read(source_name, filepath)
    
    def validate(self, source_name: str):
        assert self.vm is not None
        self.vm.validate(source_name)
    
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