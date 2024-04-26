from __future__ import annotations
import typing as t
import sys
import readline
import atexit
import os

import pandas as pd

from kye.parser import Parser
from kye.interpreter import Interpreter
from kye.errors import ErrorReporter, KyeRuntimeError

def eval_definitions(source: str, interpreter: Interpreter) -> ErrorReporter:
    reporter = ErrorReporter(source)
    parser = Parser(reporter)
    tree = parser.parse_definitions(source)
    if reporter.had_error:
        return reporter

    interpreter.reporter = reporter
    try:
        interpreter.visit(tree)
    except KyeRuntimeError as error:
        reporter.runtime_error(error)
    if reporter.had_error:
        return reporter

    return reporter

def eval_expression(source: str, interpreter: Interpreter) -> ErrorReporter:
    reporter = ErrorReporter(source)
    parser = Parser(reporter)
    tree = parser.parse_expression(source)
    if reporter.had_error:
        return reporter

    interpreter.reporter = reporter
    try:
        val = interpreter.visit(tree)
        print(val)
    except KyeRuntimeError as error:
        reporter.runtime_error(error)
    if reporter.had_error:
        return reporter

    return reporter

def setup_readline():
    histfile = os.path.join(os.path.expanduser("~"), ".kye_history")
    try:
        readline.read_history_file(histfile)
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass
    atexit.register(readline.write_history_file, histfile)

def run_prompt(interpreter):
    setup_readline()
    print("Kye REPL\n")
    while True:
        try:
            user_input = input('> ')
            if user_input.lower() == "exit":
                break
            reporter = eval_expression(user_input, interpreter)
            reporter.report()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

def run_file(file_path, tables):
    with open(file_path, "r") as file:
        source = file.read()
    interpreter = Interpreter(tables, ErrorReporter(source))
    reporter = eval_definitions(source, interpreter)
    reporter.report()
    if reporter.had_runtime_error:
        sys.exit(70)
    if reporter.had_error:
        sys.exit(65)
    return interpreter


def main():
    tables = {
        'User': pd.DataFrame([
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'},
        ])
    }
    
    if len(sys.argv) > 2:
        if sys.argv[1] == 'debug':
            interpreter = run_file(sys.argv[2], tables)
            run_prompt(interpreter)
    elif len(sys.argv) == 2:
        run_file(sys.argv[1], tables)
    
    print("Usage: kye (debug) [script]")
    sys.exit(64)