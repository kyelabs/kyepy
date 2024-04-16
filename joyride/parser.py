from __future__ import annotations
import typing as t
from pathlib import Path
from enum import Enum
import lark
import pandas as pd

class Environment:
    values: t.Dict[str, t.Any]
    enclosing: t.Optional[Environment]

    def __init__(self, enclosing: t.Optional[Environment]=None):
        self.values = {}
        self.enclosing = enclosing
    
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

    def get(self, name: str):
        raise NotImplementedError()
    
    def __str__(self):
        return self.name

class Model(Type):
    name: str
    index: t.List[str]
    block: lark.Tree
    dataframe: t.Optional[pd.DataFrame]
    edges: t.Dict[str, Edge]

    def __init__(self, name: str, index: t.List[str], dataframe: pd.DataFrame):
        self.name = name
        self.index = index
        self.dataframe = dataframe
        self.edges = {}
    
    def define(self, name: str, edge: pd.Series):
        self.edges[name] = edge
    
    def get(self, name: str):
        if name in self.edges:
            return self.edges[name]
        raise RuntimeError(f"Edge '{name}' not found in model '{self.name}'")
    
    def call(self, interpreter: Interpreter, arguments):
        assert self.dataframe is not None
        selection = self.dataframe
        for name, val in zip(self.index, arguments):
            selection = selection[selection[name] == val]
        assert len(selection) == 1, f"Expected exactly one row, got {len(selection)}"
        return selection.iloc[0]

    def arity(self):
        return len(self.index)

class Edge(Callable):
    name: str
    closure: Environment
    params: t.List[str]
    block: lark.Tree
    cardinality: Cardinality

    def __init__(self, name: str, closure: Environment, params: t.List[str], block: lark.Tree, cardinality: Cardinality):
        self.name = name
        self.closure = closure
        self.params = params
        assert block.data == 'block'
        assert block.children[-1].data == 'return_stmt'
        self.block = block
        self.cardinality = cardinality
    
    def call(self, interpreter: Interpreter, arguments):
        env = Environment(self.closure)
        for name, val in zip(self.params, arguments):
            env.define(name, val)
        result = interpreter.visit_with_env(self.block, env)
        assert type(result) is list
        return result[-1]

    def arity(self):
        return len(self.params)
    
    def __str__(self):
        return self.name

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

class Cardinality(Enum):
    ONE = '!'
    MANY = '*'
    MAYBE = '?'
    MORE = '+'

GRAMMAR = Path(__file__).parent / 'grammer.lark'

def get_parser(start):
    return lark.Lark(GRAMMAR.read_text(), parser='lalr', propagate_positions=True, start=start)

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
        return values[0] and values[1]
    elif operator == Operator.XOR:
        return values[0] ^ values[1]
    elif operator == Operator.OR:
        return values[0] or values[1]
    elif operator == Operator.NOT:
        return not values[0]
    elif operator == Operator.INV:
        return ~values[0]
    elif operator == Operator.IS:
        return values[0] is values[1]
    raise ValueError(f'Invalid operator {operator}')

def _operator(operator: Operator):
    def visit_operator(self: Interpreter, values):
        return operation(operator, self.visit_all(values))
    return visit_operator

def get_name(child: t.Union[lark.Token, lark.Tree]) -> str:
    if isinstance(child, lark.Token):
        return child.type
    return child.data

def get_children(node: lark.Tree, *names: str) -> t.List[lark.Tree]:
    return [child for child in node.children if get_name(child) in names]

def get_child(node: lark.Tree, *names: str) -> lark.Tree:
    children = get_children(node, *names)
    if not children:
        return None
    return children[0]

class Interpreter(lark.visitors.Interpreter):
    env: Environment
    data: t.Dict[str, pd.DataFrame]

    def __init__(self, env: Environment, data: t.Dict[str, pd.DataFrame]):
        self.env = env
        self.data = data
    
    def visit_with_env(self, tree: lark.Tree, env: Environment) -> t.Any:
        previous = self.env
        value = None
        try:
            self.env = env
            value = self.visit(tree)
        finally:
            self.env = previous
        return value

    def visit_all(self, values):
        return [
            self.visit(value) if isinstance(value, lark.Tree) else value
            for value in values
        ]

    def _list(self, node):
        return self.visit_all(node.children)
    
    @lark.v_args(inline=True)
    def _binary(self, value1, operator, value2):
        return operation(Operator(operator), [
            self.visit(value1),
            self.visit(value2)
        ])

    @lark.v_args(inline=True)
    def literal(self, val: lark.Token):
        if val.type == 'SIGNED_NUMBER':
            return float(val)
        if val.type == 'BOOLEAN':
            return val == 'TRUE'
        if val.type == 'STRING':
            return val[1:-1]
        raise Exception(f'Unknown token type: {val.type}({val.value})')

    add_exp = _binary
    mult_exp = _binary
    comp_exp = _binary
    and_exp = _operator(Operator.AND)
    xor_exp = _operator(Operator.XOR)
    or_exp = _operator(Operator.OR)
    is_exp = _operator(Operator.IS)

    block = _list
    statement = _list
    index = _list
    return_stmt = lambda self, value: self.visit(value.children[0])

    def model_def(self, model_def: lark.Tree):
        name = get_child(model_def, 'TYPE')
        format = get_child(model_def, 'FORMAT')
        indexes = self.visit_all(get_children(model_def, 'index'))
        block: lark.Tree = model_def.children[-1]
        assert len(indexes) == 1
        assert name in self.data
        data = self.data[name]
        model = Model(name, indexes[0], data)
        self.env.define(name, model)
        previous = self.env
        self.env = Environment(previous)
        self.env.define('this', model)
        self.visit(block)
        self.env = previous

    def edge_def(self, edge_def: lark.Tree):
        name = get_child(edge_def, 'EDGE')
        indexes = self.visit_all(get_children(edge_def, 'index'))
        assert len(indexes) == 0
        cardinality = Cardinality(get_child(edge_def, 'CARDINALITY') or '!')
        model = self.env.get('this')
        assert isinstance(model, Model)
        assert name in model.dataframe.columns
        actual_value: pd.Series = model.dataframe[name]
        expected_value = self.visit(edge_def.children[-1])
        if isinstance(expected_value, Type):
            pass
        else:
            assert (actual_value == expected_value).all()
        self.env.define(name, actual_value)
    
    @lark.v_args(inline=True)
    def edge_identifier(self, name):
        return self.env.get(name)

    def call_exp(self, call_exp: lark.Tree):
        edge = self.visit(call_exp.children[0])
        assert isinstance(edge, Callable)
        arguments = self.visit_all(call_exp.children[1:])
        assert len(arguments) == edge.arity()
        return edge.call(self, arguments)


if __name__ == '__main__':
    definitions_parser = get_parser('statements')
    tree = definitions_parser.parse('''
    User(id) {
        id: 1
    }
    ''')
    print(tree)
    env = Environment()
    interpreter = Interpreter(env, data={
        'User': pd.DataFrame([
            {'id': 1}
        ])
    })
    result = interpreter.visit(tree)
    print('hi')

    # expressions_parser = get_parser('exp')
    # tree = expressions_parser.parse('FALSE & 1 + 2 * 3')
    # env = Environment()
    # df = pd.DataFrame([
    #     {'a': 1, 'b': 2},
    #     {'a': 3, 'b': 4},
    #     {'a': 5, 'b': 6}
    # ])
    # env.define('self', df)
    # interpreter = Interpreter(env)
    # result = interpreter.visit(tree)
    # print(result)
    # print('hi')