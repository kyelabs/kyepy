from __future__ import annotations
import typing as t
import sys
import readline
import atexit
import os

from kye.kye import Kye

if t.TYPE_CHECKING:
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

def run_prompt(kye):
    import ibis
    ibis.options.interactive = True
    setup_readline()
    print("Kye REPL\n")
    while True:
        try:
            user_input = input('> ')
            if user_input.lower() == "exit":
                break
            val = kye.eval_expression(user_input)
            if kye.reporter.had_error:
                kye.reporter.report()
            else:
                print(val)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

def run_file(file_path, kye: Kye):
    with open(file_path, "r") as file:
        source = file.read()
    kye.eval_definitions(source)
    kye.reporter.report()
    if kye.reporter.had_runtime_error:
        sys.exit(70)
    if kye.reporter.had_error:
        sys.exit(65)


def main():
    kye = Kye()
    
    if len(sys.argv) > 2:
        if sys.argv[1] == 'debug':
            run_file(sys.argv[2], kye)
            run_prompt(kye)
    elif len(sys.argv) == 2:
        run_file(sys.argv[1], kye)
    else:
        print("Usage: kye (debug) [script]")
    
    sys.exit(64)

if __name__ == "__main__":
    main()