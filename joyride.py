from joyride.parser import parse_definitions, parse_expression
from joyride.interpreter import Interpreter
import pandas as pd


if __name__ == '__main__':
    interpreter = Interpreter({
        'User': pd.DataFrame([
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'},
        ])
    })
    interpreter.visit(parse_definitions('''
    User(id) {
        id: Number
    }
    '''))
    r = interpreter.visit(parse_expression('''
    User.id
    '''))
    # builder = Builder()
    # e = builder.transform(ast_tree)
    print(r)
    print('hi')