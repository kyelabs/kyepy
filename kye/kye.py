import typing as t
from dataclasses import dataclass
from pathlib import Path

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.parse.parser import Parser
from kye.type.type_builder import TypeBuilder
from kye.vm.loader import Loader
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.compiler import compile, write_compiled
from kye.vm.vm import VM

@dataclass
class Config:
    kye_file: str
    data_file: t.Optional[str] = None
    model_name: t.Optional[str] = None
    compiled_out: t.Optional[str] = None

class Kye:
    reporter: ErrorReporter
    type_builder: TypeBuilder
    vm: VM

    def __init__(self, config: Config):
        self.config = config
        self.type_builder = TypeBuilder()
    
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
    
    def eval_definitions(self, source: str) -> bool:
        tree = self.parse_definitions(source)
        types = self.build_types(tree)
        if types is None:
            return False
        compiled = compile(types)
        if self.config.compiled_out is not None:
            write_compiled(compiled, self.config.compiled_out)
        if self.config.model_name is not None:
            loader = Loader(compiled, self.reporter)
            assert self.config.data_file is not None
            loader.read(self.config.model_name, self.config.data_file)
            self.vm = VM(loader)
            self.vm.reporter = self.reporter
            self.vm.validate(self.config.model_name)
        return not self.reporter.had_error
    
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