from __future__ import annotations
import typing as t
import sys
from argparse import ArgumentParser
# import readline
# import atexit
# import os

from kye.kye import Kye
from kye.__about__ import __version__

# def setup_readline():
#     histfile = os.path.join(os.path.expanduser("~"), ".kye_history")
#     try:
#         readline.read_history_file(histfile)
#         readline.set_history_length(1000)
#     except FileNotFoundError:
#         pass
#     atexit.register(readline.write_history_file, histfile)

# def run_prompt(kye):
#     setup_readline()
#     print("Kye REPL\n")
#     while True:
#         try:
#             user_input = input('> ')
#             if user_input.lower() == "exit":
#                 break
#             val = kye.eval_expression(user_input)
#             if kye.reporter.had_error:
#                 kye.reporter.report()
#             else:
#                 print(val)
#         except EOFError:
#             print()
#             break
#         except KeyboardInterrupt:
#             print()
#             continue

def compile_script(file_path, kye: Kye):
    with open(file_path, "r") as file:
        source = file.read()
    kye.compile(source)
    kye.reporter.report()
    if kye.reporter.had_error:
        sys.exit(65)


parser = ArgumentParser(description="Kye programming language")
parser.add_argument("script", nargs='?',
                    help="Script to run")
parser.add_argument('-d','--data', dest='data_file',
                    help="Data file to load")
parser.add_argument('-m','--model', dest='model_name',
                    help="Model to load")
parser.add_argument('-c','--compiled', dest='compiled_out',
                    help="Output compiled file")
parser.add_argument('-v','--version', action='version', version=__version__)


def main():
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    
    args = parser.parse_args()
    
    kye = Kye()
    success = kye.read(args.script)
    if not success:
        kye.reporter.report()
        sys.exit(65)
    
    if args.compiled_out is not None:
        kye.write_compiled(args.compiled_out)
    
    if args.model_name is not None:
        assert args.data_file is not None
        kye.load_file(args.model_name, args.data_file)
        if kye.reporter.had_error:
            kye.reporter.report()
            sys.exit(65)

if __name__ == "__main__":
    main()