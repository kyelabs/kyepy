import typing as t

from kye.parse.parser import Parser
from kye.parse.expressions import Node
from kye.interpreter import Interpreter
from kye.type.type_builder import TypeBuilder
from kye.errors import ErrorReporter, KyeRuntimeError
from kye.engine import Engine

class Kye:
    engine: Engine
    reporter: ErrorReporter
    interpreter: Interpreter

    def __init__(self):
        self.engine = Engine()
        self.interpreter = Interpreter(self.engine)
    
    def eval_definitions(self, source: str) -> bool:
        self.reporter = ErrorReporter(source)
        parser = Parser(self.reporter)
        tree = parser.parse_definitions(source)
        self._eval_ast(tree)
        return not self.reporter.had_error
    
    def eval_expression(self, source: str) -> t.Any:
        self.reporter = ErrorReporter(source)
        parser = Parser(self.reporter)
        tree = parser.parse_expression(source)
        return self._eval_ast(tree)
    
    def _eval_ast(self, tree: Node) -> t.Any:
        if self.reporter.had_error:
            return
        type_builder = TypeBuilder(self.reporter)
        type_builder.visit(tree)
        types = type_builder.types

        if self.reporter.had_error:
            return
        self.interpreter.reporter = self.reporter
        try:
            return self.interpreter.visit(tree)
        except KyeRuntimeError as error:
            self.reporter.runtime_error(error)