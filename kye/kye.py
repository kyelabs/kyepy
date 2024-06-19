import typing as t

import kye.parse.expressions as ast
import kye.type.types as typ
from kye.parse.parser import Parser
from kye.interpreter import Interpreter
from kye.type.type_builder import TypeBuilder
from kye.load.loader import Loader
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.engine import Engine

class Kye:
    engine: Engine
    reporter: ErrorReporter
    type_builder: TypeBuilder
    interpreter: Interpreter

    def __init__(self):
        self.engine = Engine()
        self.type_builder = TypeBuilder()
    
    def parse_definitions(self, source: str) -> t.Optional[ast.Script]:
        """ Parse definitions from source code """
        self.reporter = ErrorReporter(source)
        parser = Parser(self.reporter)
        tree = parser.parse_definitions(source)
        if self.reporter.had_error:
            return None
        return tree

    def parse_expression(self, source: str) -> t.Optional[ast.Expr]:
        """ Parse an expression from source code """
        self.reporter = ErrorReporter(source)
        parser = Parser(self.reporter)
        tree = parser.parse_expression(source)
        if self.reporter.had_error:
            return None
        return tree

    def build_types(self, tree: t.Optional[ast.Node]) -> t.Optional[typ.Types]:
        """ Build types from the AST """
        if tree is None:
            return None
        self.type_builder.reporter = self.reporter
        self.type_builder.visit(tree)
        if self.reporter.had_error:
            return None
        if self.reporter.had_error:
            return None
        return self.type_builder.types
    
    def eval_definitions(self, source: str) -> bool:
        tree = self.parse_definitions(source)
        types = self.build_types(tree)
        if types is None:
            return False
        loader = Loader(types, self.engine, self.reporter)
        self.interpreter = Interpreter(types, loader)
        return not self.reporter.had_error
    
    def eval_expression(self, source: str) -> t.Any:
        assert self.interpreter is not None
        tree = self.parse_expression(source)
        self.build_types(tree)
        self.interpreter.reporter = self.reporter
        if tree is None:
            return None
        try:
            return self.interpreter.visit(tree)
        except KyeRuntimeError as error:
            self.reporter.runtime_error(error)