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
    
    def parse(self, interpreter: Interpreter, val: t.Any, format: t.Optional[str]) -> t.Any:
        raise NotImplementedError()
    
    def get_edge(self, name: str):
        raise NotImplementedError()
    
    def list_edges(self) -> t.Set[str]:
        raise NotImplementedError()
    
    def __str__(self):
        return self.name

class Abstract(Type):
    pass

class Number(Abstract):
    name = 'Number'

    def parse(self, interpreter: Interpreter, val: t.Any, format: t.Optional[str]):
        if isinstance(val, pd.Series):
            assert val.empty or pd.api.types.is_numeric_dtype(val)
            return val
        return float(val)
    
    def list_edges(self) -> t.Set[str]:
        return set()

    def call(self, interpreter: Interpreter, arguments):
        return float(arguments[0])

    def arity(self):
        return 1

class String(Abstract):
    name = 'String'

    def parse(self, interpreter: Interpreter, val: t.Any, format: t.Optional[str]):
        if isinstance(val, pd.Series):
            assert val.empty or pd.api.types.is_string_dtype(val)
            return val
        return str(val)

    def list_edges(self) -> t.List[str]:
        return ['length']

    def call(self, interpreter: Interpreter, arguments):
        return str(arguments[0])

    def arity(self):
        return 1

class Boolean(Abstract):
    name = 'Boolean'

    def parse(self, interpreter: Interpreter, val: t.Any, format: t.Optional[str]):
        if isinstance(val, pd.Series):
            assert val.empty or pd.api.types.is_bool_dtype(val)
            return val
        return bool(val)
    
    def list_edges(self) -> t.Set[str]:
        return set()

    def call(self, interpreter: Interpreter, arguments):
        return bool(arguments[0])

    def arity(self):
        return 1

def normalize_column(s: pd.Series) -> pd.Series:
    t = s.explode().dropna().infer_objects()
    return t.groupby(t.index).unique()

def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([
        normalize_column(frame[col])
        for col in frame.columns
    ], axis=1)

class Model(Type):
    name: str
    index: t.List[str]
    env: Environment
    conditions: t.List[lark.Tree]
    frame: pd.DataFrame
    edges: t.Dict[str, Edge]

    def __init__(self, name: str, index: t.List[str], env: Environment):
        self.name = name
        self.index = index
        self.env = env
        self.conditions = []
        self.frame = pd.DataFrame()
        self.edges = {}
        self.env.define('this', self)
    
    def define_edge(self, edge: Edge):
        assert edge.name not in self.edges
        assert isinstance(edge, Edge)
        self.edges[edge.name] = edge
        self.env.define(edge.name, edge)
    
    def get_edge(self, name: str) -> Edge:
        if name not in self.edges:
            raise RuntimeError(f"Edge '{name}' not found in model '{self.name}'")
        return self.edges[name]

    def list_edges(self):
        return set(self.edges.keys())

    def parse_edge(self, interpreter: Interpreter, edge_name: str, val: pd.Series) -> pd.Series:
        val = val.explode().dropna().infer_objects()
        val = self.edges[edge_name].parse(interpreter, val, None)
        val = val.groupby(val.index).unique()
        val.name = edge_name
        return val
    
    def parse(self, interpreter: Interpreter, raw_val: t.Any, format: t.Optional[str]):
        def is_series_of_dicts(s: pd.Series):
            return s.sample(min(len(s),100)).apply(lambda n: type(n) is dict).all()
        val: pd.DataFrame
        if isinstance(raw_val, pd.Series) and is_series_of_dicts(raw_val):
            val = pd.DataFrame(raw_val.tolist(), index=raw_val.index)
        elif isinstance(raw_val, list):
            val = pd.DataFrame(raw_val)
        elif isinstance(raw_val, dict):
            val = pd.Series(raw_val).to_frame().T
        elif isinstance(raw_val, pd.DataFrame):
            val = raw_val
        assert isinstance(val, pd.DataFrame)

        # Edge assertions should only be testing the actual values
        # and not the structure of the data frame
        frame = pd.concat([
            self.parse_edge(interpreter, edge, val[edge])
            for edge in self.list_edges()
            if edge in val.columns
        ], axis=1)
        
        # After the frame has been parsed, we can group by the index
        for col in self.index:
            assert col in frame.columns, f"Index column '{col}' not found in frame."
            frame = frame.explode(column=col)
        grouped = frame.set_index(self.index)

        # Update our frame if it contains more than just index columns
        if not grouped.empty:
            self.frame = normalize_frame(pd.concat([self.frame, grouped]))

            for condition in self.conditions:
                assert interpreter.visit(condition)

        # Return the index columns
        return pd.Series(
            t.cast(t.List, frame[self.index].itertuples(index=False, name=None)),
            index=frame.index
        )

    @t.overload
    def select(self, keys: t.List[t.Any]) -> pd.DataFrame: ...

    @t.overload
    def select(self, keys: pd.Series) -> pd.DataFrame: ...

    def select(self, keys) -> pd.DataFrame:
        if isinstance(keys, pd.Series):
            return self.frame.loc[keys[keys.isin(self.frame.index)]].reindex(keys)
        if isinstance(keys, list):
            if isinstance(self.frame.index, pd.MultiIndex):
                if tuple(keys) in self.frame.index:
                    return t.cast(pd.Series, self.frame.loc[tuple(keys)]).to_frame().T
            elif len(keys) == 1 and keys[0] in self.frame.index:
                return t.cast(pd.Series, self.frame.loc[keys[0]]).to_frame().T
        return self.frame.query('0 == 1')
    
    def contains(self, val: t.Any):
        if len(self.index) != 1:
            raise NotImplementedError()
        selection = self.select([val,])
        return not selection.empty
    
    def call(self, interpreter: Interpreter, arguments):
        selection = self.select(arguments)
        assert len(selection) == 1, f"Expected exactly one row, got {len(selection)}"
        return selection

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
    
    def parse(self, interpreter: Interpreter, val: pd.Series, format: t.Optional[str]):
        assert isinstance(val, pd.Series)
        assert self.arity() ==  0
        if val.empty:
            return val
        expected_value = self.call(interpreter, [])
        if isinstance(expected_value, Type):
            return expected_value.parse(interpreter, val, None)
        else:
            assert (val == expected_value).all()
            return val
    
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
    data: t.Dict[str, t.Any]

    def __init__(self, env: Environment, data: t.Dict[str, t.Any]):
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
        indexes = self.visit_all(find_children(model_def, 'index'))
        block = get_child_by_index(model_def, -1)
        assert len(indexes) == 1
        assert name in self.data
        model = Model(name, indexes[0], Environment(self.env))
        self.env.define(name, model)

        for stmt in iter_children(block):
            if stmt.data == 'edge_def':
                edge = self._edge_def(stmt)
                model.define_edge(edge)
            else:
                raise NotImplementedError()
        
        data = self.data[name]
        model.parse(self, data, None)
    
    def _edge_def(self, edge_def: lark.Tree):
        name = get_token(edge_def, 'EDGE')
        indexes = self.visit_all(find_children(edge_def, 'index'))
        params = indexes[0] if len(indexes) > 0 else []
        cardinality = Cardinality(find_token(edge_def, 'CARDINALITY') or '!')
        exp = get_child_by_index(edge_def, -1)
        
        if exp.data != 'block':
            exp = lark.Tree('block', [lark.Tree('return_stmt', [exp])])
        
        edge = Edge(name, Environment(self.env), params, exp, cardinality)
        return edge

    def edge_def(self, edge_def: lark.Tree):
        edge = self._edge_def(edge_def)
        self.env.define(edge.name, edge)
    
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
    # interpreter = Interpreter(env, data={
    #     'User': pd.DataFrame([
    #         {'id': 1}
    #     ])
    # })
    interpreter = Interpreter(env, data={
        'User': [
            {'id': 1, 'name': 'alice', 'friends': [
                {'id': 2, 'name': 'bob'},
                {'id': 3, 'name': 'charlie'},
            ]},
        ]
    })
    interpreter.visit(definitions_parser.parse('''
    User(id) {
        id: Number
        name: String
        friends*: User
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