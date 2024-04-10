from __future__ import annotations
import typing as t
from pathlib import Path
from enum import Enum
from lark import Lark, Transformer, Tree, Token
import pandas as pd

class Environment:
    values: t.Dict[str, t.Any]
    enclosing: t.Optional[Environment]

    def __init__(self, enclosing: t.Optional[Environment]=None):
        self.values = {}
        self.enclosing = enclosing
    
    def create_child(self) -> Environment:
        return Environment(self)
    
    def get_owner(self, name: str) -> t.Optional[Environment]:
        if name in self.values:
            return self
        if self.enclosing is not None:
            return self.enclosing.get_owner(name)
        return None

    def define(self, name: str, value: t.Any):
        if name in self.values:
            raise RuntimeError(f'Variable "{name}" already defined.')
        self.values[name] = value
    
    def get(self, name: str) -> t.Any:
        owner = self.get_owner(name)
        if owner is None:
            raise RuntimeError(f"Undefined variable '{name}'.")
        return owner.values.get(name)

    def has(self, name: str) -> bool:
        return self.get_owner(name) is not None

class Callable:
    """ Abstract class for callables """
    def call(self, interpreter: Interpreter, arguments):
        raise NotImplementedError()

    def arity(self):
        raise NotImplementedError()

    def __str__(self):
        return "<callable>"

class Type(Callable):
    """ Abstract class for types/tables/models """
    name: str
    parent: t.Optional[Type]
    edges: t.List[Type]
    
    def __init__(self, name: str):
        self.name = name

class Edge(Callable):
    closure: Environment
    declaration: Tree

    def __init__(self, closure: Environment, declaration: Tree):
        self.closure = closure
        self.declaration = declaration
    
    def call(self, interpreter: Interpreter, arguments):
        env = self.closure.create_child()
        self.declaration.children[0].children
        for i, param in enumerate(self.declaration.children):
            env.define(param, arguments[i])


class Const:
    type: Type
    value: t.Any

    def __init__(self, type: Type, value: t.Any):
        self.type = type
        self.value = value


class Operator(Enum):
    ADD = '+'
    SUB = '-'
    MUL = '*'
    DIV = '/'
    MOD = '%'
    POW = '^'
    EQ = '=='
    NE = '!='
    LT = '<'
    GT = '>'
    LE = '<='
    GE = '>='
    AND = '&'
    XOR = '^'
    OR = '|'
    NOT = '!'
    INV = '~'
    IS = 'is'

GRAMMAR = Path(__file__).parent / 'grammer.lark'

def get_parser(start):
    return Lark(GRAMMAR.read_text(), parser='lalr', propagate_positions=True, start=start)

def operator_token(self, token):
    return Operator(token[0])

def get_binary_operation(operator: Operator):
    def binary_operation(self, values):
        return operation(operator, values)
    return binary_operation

def binary_operation(self, children):
    value1, operator, value2 = children
    return operation(operator, [value1, value2])

def get_name(child: t.Union[Tree, Token]):
    if isinstance(child, Token):
        return child.type
    return child.data

def get_children(children: t.List[t.Union[Tree, Token]], *names: str):
    return [child for child in children if get_name(child) in names]

def get_child(children: t.List[t.Union[Tree, Token]], *names: str):
    found = get_children(children, *names)
    if not found:
        return None
    return found[0]

def operation(operator: Operator, values: t.List[t.Any]):
    if operator == Operator.ADD:
        return values[0] + values[1]
    elif operator == Operator.SUB:
        return values[0] - values[1]
    elif operator == Operator.MUL:
        return values[0] * values[1]
    elif operator == Operator.DIV:
        return values[0] / values[1]
    elif operator == Operator.MOD:
        return values[0] % values[1]
    elif operator == Operator.EQ:
        return values[0] == values[1]
    elif operator == Operator.NE:
        return values[0] != values[1]
    elif operator == Operator.LT:
        return values[0] < values[1]
    elif operator == Operator.GT:
        return values[0] > values[1]
    elif operator == Operator.LE:
        return values[0] <= values[1]
    elif operator == Operator.GE:
        return values[0] >= values[1]
    elif operator == Operator.AND:
        return values[0] & values[1]
    elif operator == Operator.XOR:
        return values[0] ^ values[1]
    elif operator == Operator.OR:
        return values[0] | values[1]
    elif operator == Operator.NOT:
        return not values[0]
    elif operator == Operator.INV:
        return ~values[0]
    elif operator == Operator.IS:
        return values[0] is values[1]
    raise ValueError(f'Invalid operator {operator}')


class Interpreter(Transformer):
    def __init__(self, env: Environment):
        self.global_env = env
        self.current_env = env
    
    def _execute_block(self, tree: Tree, env: Environment) -> t.Any:
        previous = self.current_env
        value = None
        try:
            self.current_env = env
            value = self.transform(tree)
        finally:
            self.current_env = previous
        return value

    SIGNED_NUMBER = lambda self, token: float(token[0])
    BOOLEAN = lambda self, token: token[0] == 'TRUE'
    STRING = lambda self, token: token[0][1:-1]
    UNARY_OP = operator_token
    ADDITION_OP = operator_token
    MULTIPLICATION_OP = operator_token
    COMPARISON_OP = operator_token

    literal = lambda self, token: token[0]
    add_exp = binary_operation
    mult_exp = binary_operation
    comp_exp = binary_operation
    and_exp = get_binary_operation(Operator.AND)
    xor_exp = get_binary_operation(Operator.XOR)
    or_exp = get_binary_operation(Operator.OR)
    is_exp = get_binary_operation(Operator.IS)

if __name__ == '__main__':
    definitions_parser = get_parser('statements')
    tree = definitions_parser.parse('''
    # name(param1, param2)(param2): type + 1
    name(param1, param2)+ {
        return param1
    }
    ''')
    edge = get_child(tree.children, 'edge_def')
    name = get_child(edge.children, 'EDGE')
    cardinality = get_child(edge.children, 'CARDINALITY')
    indexes = get_children(edge.children, 'index')
    print(name, cardinality, indexes)
    print('hi')
    # expressions_parser = get_parser('exp')
    # tree = expressions_parser.parse('1 + 2 * 3')
    # env = Environment()
    # df = pd.DataFrame([
    #     {'a': 1, 'b': 2},
    #     {'a': 3, 'b': 4},
    #     {'a': 5, 'b': 6}
    # ])
    # env.define('self', df)
    # evaluator = Interpreter(env)
    # tree = evaluator.transform(tree)
    # print(tree)
    # print('hi')