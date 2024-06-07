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
    interpreter: Interpreter

    def __init__(self):
        self.engine = Engine()
        self.type_builder = TypeBuilder()
        self.interpreter = Interpreter(self.engine)
        self.loader = Loader(self.engine)
    
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
        # Load the types
        self.loader.reporter = self.reporter
        self.loader.load(self.type_builder.types)
        if self.reporter.had_error:
            return None
        return self.type_builder.types

    def eval_tree(self, tree: t.Optional[ast.Node]) -> t.Optional[t.Any]:
        """ Evaluate the AST """
        if tree is None:
            return None
        self.build_types(tree)
        self.interpreter.reporter = self.reporter
        try:
            return self.interpreter.visit(tree)
        except KyeRuntimeError as error:
            self.reporter.runtime_error(error)
        return None
    
    def eval_definitions(self, source: str) -> bool:
        tree = self.parse_definitions(source)
        self.eval_tree(tree)
        return not self.reporter.had_error
    
    def eval_expression(self, source: str) -> t.Any:
        tree = self.parse_expression(source)        
        return self.eval_tree(tree)