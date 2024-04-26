from __future__ import annotations
import typing as t
import sys

import pandas as pd

from joyride.parser import Parser
from joyride.interpreter import Interpreter
from joyride.errors import ErrorReporter, KyeRuntimeError

def eval(source: str, data: t.Dict[str, pd.DataFrame]) -> ErrorReporter:
    reporter = ErrorReporter(source)
    parser = Parser(reporter)
    tree = parser.parse_definitions(source)
    if reporter.had_error:
        return reporter

    interpreter = Interpreter(data, reporter)
    try:
        interpreter.visit(tree)
    except KyeRuntimeError as error:
        reporter.runtime_error(error)
    if reporter.had_error:
        return reporter

    return reporter


if __name__ == '__main__':
    DATA = {
        'User': pd.DataFrame([
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'},
        ])
    }
    
    reporter = eval('''
    User(id) {
        id: Number
        name: String
    }
    ''', DATA)

    if reporter.had_error:
        reporter.report()

    print('hi')