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

    def define(self, name: t.Union[str, lark.Token], value: t.Any):
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
    
    def contains(self, val: t.Any) -> bool:
        raise NotImplementedError()
    
    def allows(self, interpreter: Interpreter, val: t.Any) -> bool:
        raise NotImplementedError()

    def get_edge(self, name: str):
        raise NotImplementedError()
    
    def list_edges(self) -> t.Set[str]:
        raise NotImplementedError()
    
    def __str__(self):
        return self.name

class Abstract(Type):
    def allows(self, interpreter: Interpreter, val: t.Any) -> bool:
        return self.contains(val)

class Number(Abstract):
    name = 'Number'

    def contains(self, val: t.Any):
        try:
            float(val)
            return True
        except:
            return False
    
    def list_edges(self) -> t.Set[str]:
        return set()

    def call(self, interpreter: Interpreter, arguments):
        return float(arguments[0])

    def arity(self):
        return 1

class String(Abstract):
    name = 'String'

    def contains(self, val: t.Any):
        return True

    def list_edges(self) -> t.List[str]:
        return ['length']

    def call(self, interpreter: Interpreter, arguments):
        return str(arguments[0])

    def arity(self):
        return 1

class Boolean(Abstract):
    name = 'Boolean'

    def contains(self, val: t.Any):
        return True
    
    def list_edges(self) -> t.Set[str]:
        return set()

    def call(self, interpreter: Interpreter, arguments):
        return bool(arguments[0])

    def arity(self):
        return 1

class Model(Type):
    name: str
    index: t.List[str]
    env: Environment
    conditions: t.List[lark.Tree]
    frame: pd.DataFrame

    def __init__(self, name: str, index: t.List[str], env: Environment):
        self.name = name
        self.index = index
        self.env = env
        self.conditions = []
        self.frame = pd.DataFrame()
    
    def get_edge(self, name: str):
        if name in self.frame.columns:
            return self.frame[name].explode().dropna().infer_objects().groupby(level=0).unique()
        raise RuntimeError(f"Edge '{name}' not found in model '{self.name}'")

    def list_edges(self):
        return set(self.frame.columns)

    def _select(self, keys: t.List[t.Any]) -> pd.DataFrame:
        selection = pd.Series(True, index=self.frame.index)
        assert len(self.index) == len(keys)
        for name, val in zip(self.index, keys):
            selection &= self.get_edge(name) == val
        return self.frame[selection]
    
    def _merge_frame(self, other: pd.DataFrame) -> pd.DataFrame:
        def normalize_columns(s: pd.Series):
            t = s.explode().dropna().infer_objects()
            return t.groupby(t.index).unique()
        combined = pd.concat([self.frame, other], ignore_index=True)
        for col in self.index:
            combined = combined.explode(column=col)
        combined = combined.set_index(self.index)
        if not combined.empty:
            combined = pd.concat([
                normalize_columns(combined[col])
                for col in combined.columns
            ], axis=1)
        combined.index.names = self.index
        return combined.reset_index()
    
    def allows(self, interpreter: Interpreter, val: t.Any):
        assert isinstance(val, pd.DataFrame)
        for column in val.columns:
            if not self.env.has(column):
                # TODO: Warn about unknown column
                continue
            edge = self.env.get(column)
            assert isinstance(edge, Edge)
            edge.allows(interpreter, val)
        for condition in self.conditions:
            assert interpreter.visit(condition)
        self.frame = self._merge_frame(val)
    
    def contains(self, val: t.Any):
        if len(self.index) != 1:
            raise NotImplementedError()
        selection = self._select([val])
        return not selection.empty
    
    def call(self, interpreter: Interpreter, arguments):
        selection = self._select(arguments)
        assert len(selection) == 1, f"Expected exactly one row, got {len(selection)}"
        return selection.iloc[0]

    def arity(self):
        return len(self.index)

# class SubModel(Type):
#     parent: Type
#     conditions: t.List[lark.Tree]
#     edges: t.Dict[str, pd.Series]

#     def __init__(self, parent: Type, condition: lark.Tree):
#         self.parent = parent
#         self.condition = condition
    
#     def define(self, name: str, edge: pd.Series):
#         self.edges[name] = edge
    
#     def get_edge(self, name: str):
#         if name in self.edges:
#             return self.edges[name]
#         return self.parent.get_edge(name)
    
#     def list_edges(self) -> t.Set[str]:
#         return set(self.edges.keys()) | self.parent.list_edges()

#     def has(self, interpreter: Interpreter, val: t.Any):
#         if not self.parent.has(interpreter, val):
#             return False
#         env = Environment(interpreter.env)
#         for edge in self.list_edges():
#             env.define(edge, self.get_edge(edge))
#         return interpreter.visit_with_env(self.condition, env)
        

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
        assert t.cast(lark.Tree, block.children[-1]).data == 'return_stmt'
        self.block = block
        self.cardinality = cardinality
    
    def allows(self, interpreter: Interpreter, val: t.Any):
        assert isinstance(val, pd.DataFrame)
        previous = interpreter.env
        interpreter.env = Environment(self.closure)
        interpreter.env.define('this', val)
        assert self.arity() == 1
        actual_value = val[self.name]
        expected_value = self.call(interpreter, [val])
        if isinstance(expected_value, Type):
            for index, val in actual_value.iteritems():
                assert expected_value.allows(interpreter, val)
        else:
            assert (actual_value == expected_value).all()
    
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

GRAMMAR = Path(__file__).parent / 'grammar.lark'

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

Ast = t.Union[lark.Tree, lark.Token]

def iter_children(node: Ast) -> t.Iterator[lark.Tree]:
    if isinstance(node, lark.Tree):
        for child in node.children:
            if isinstance(child, lark.Tree):
                yield child

def iter_tokens(node: Ast) -> t.Iterator[lark.Token]:
    if isinstance(node, lark.Tree):
        for child in node.children:
            if isinstance(child, lark.Token):
                yield child

def find_children(node: Ast, *names: str) -> t.List[lark.Tree]:
    return [
        child
        for child in iter_children(node)
        if child.data in names
    ]

def find_tokens(node: Ast, *names: str) -> t.List[lark.Token]:
    return [
        token
        for token in iter_tokens(node)
        if token.type in names
    ]

def find_child(node: Ast, *names: str) -> t.Optional[lark.Tree]:
    for child in iter_children(node):
        if child.data in names:
            return child
    return None

def find_token(node: Ast, *names: str) -> t.Optional[lark.Token]:
    for token in iter_tokens(node):
        if token.type in names:
            return token
    return None

def get_token(node: Ast, *names: str) -> lark.Token:
    token = find_token(node, *names)
    if token is None:
        raise ValueError(f'Token {names} not found.')
    return token

def get_child_by_index(node: Ast, index: int) -> lark.Tree:
    children = list(iter_children(node))
    if (index < 0 and abs(index) > len(children)) or index >= len(children):
        raise IndexError(f'Index {index} out of bounds.')
    return children[index]

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

    def _list(self, node: lark.Tree):
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
        name = get_token(model_def, 'TYPE')
        format = find_token(model_def, 'FORMAT')
        indexes = self.visit_all(find_children(model_def, 'index'))
        block = get_child_by_index(model_def, -1)
        assert len(indexes) == 1
        assert name in self.data
        model = Model(name, indexes[0], Environment(self.env))
        model.env.define('this', model)
        self.env.define(name, model)
        self.visit_with_env(block, model.env)
        data = self.data[name]
        model.allows(self, data)

    def edge_def(self, edge_def: lark.Tree):
        name = get_token(edge_def, 'EDGE')
        indexes = self.visit_all(find_children(edge_def, 'index'))
        params = indexes[0] if len(indexes) > 0 else []
        cardinality = Cardinality(find_token(edge_def, 'CARDINALITY') or '!')
        exp = get_child_by_index(edge_def, -1)

        if self.env.has('this'):
            params = ['this', *params]
        
        if exp.data != 'block':
            exp = lark.Tree('block', [lark.Tree('return_stmt', [exp])])
        
        edge = Edge(name, Environment(self.env), params, exp, cardinality)
        self.env.define(name, edge)
    
    @lark.v_args(inline=True)
    def edge_identifier(self, name):
        return self.env.get(name)
    
    @lark.v_args(inline=True)
    def type_identifier(self, name, format=None):
        if format is not None:
            raise NotImplementedError()
        return self.env.get(name)

    def call_exp(self, call_exp: lark.Tree):
        edge = self.visit(get_child_by_index(call_exp, 0))
        assert isinstance(edge, Callable)
        arguments = self.visit_all(list(iter_children(call_exp))[1:])
        assert len(arguments) == edge.arity()
        return edge.call(self, arguments)


if __name__ == '__main__':
    definitions_parser = get_parser('statements')
    expressions_parser = get_parser('exp')
    env = Environment()
    env.define('Number', Number())
    env.define('String', String())
    env.define('Boolean', Boolean())
    interpreter = Interpreter(env, data={
        'User': pd.DataFrame([
            {'id': 1}
        ])
    })
    interpreter.visit(definitions_parser.parse('''
    User(id) {
        id: Number
    }
    '''))
    result = interpreter.visit(expressions_parser.parse('''
    User(1)
    '''))
    print(result)
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