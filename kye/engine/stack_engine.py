from __future__ import annotations
import pandas as pd
import numpy as np
# import kye.compiler.models as Models
import typing as t

Literal = t.Union[int, str, float]

def op(op: str):
    def wrapped(fn) -> t.Callable[[Edge, t.Any], Edge]:
        def wrapper(self: Edge, *args) -> Edge:
            self.col = fn(self.col, *[
                arg.col if isinstance(arg, self.__class__) else arg
                for arg in args
            ])
            self.trace += ((op, args),)
            return self
        return wrapper
    return wrapped

class Edge:
    col: pd.Series

    def __init__(self, col: pd.Series, trace:tuple=None):
        assert isinstance(col, pd.Series)
        if col.dtype == 'object':
            col = col.explode().dropna().infer_objects()
        self.col = col
        self.trace = trace or (('get', [col.name]),)
    
    @property
    def is_unique_index(self):
        return self.col.index.is_unique
    
    def dup(self):
        return self.__class__(self.col, self.trace)

    def __repr__(self):
        out = None
        for op, args in self.trace:
            if op == 'get':
                assert type(args[0]) is str
                out = args[0]
            else:
                args = [repr(arg) for arg in args]
                if out is not None:
                    args = [out, *args]
                out = '{}({})'.format(op, ','.join(args))
        return out
    
    @op('eq')
    def __eq__(col, other): return col == other

    @op('ne')
    def __ne__(col, other): return col != other

    @op('lt')
    def __lt__(col, other): return col < other

    @op('le')
    def __le__(col, other): return col <= other
    
    @op('gt')
    def __gt__(col, other): return col > other

    @op('ge')
    def __ge__(col, other): return col >= other

    @op('and')
    def __and__(col, other): return col & other

    @op('or')
    def __or__(col, other): return col | other

    @op('not')
    def __invert__(col): return ~col

    @op('xor')
    def __xor__(col, other): return col ^ other

    @op('add')
    def __add__(col, other): return col + other

    @op('sub')
    def __sub__(col, other): return col - other

    @op('mul')
    def __mul__(col, other): return col * other

    @op('div')
    def __truediv__(col, other): return col / other

    @op('mod')
    def __mod__(col, other): return col % other

    @op('all')
    def all(col): return col.groupby(level=0).all()

    @op('any')
    def any(col): return col.groupby(level=0).any()

    @op('sum')
    def sum(col): return col.groupby(level=0).sum()

    @op('avg')
    def mean(col): return col.groupby(level=0).mean()

    @op('min')
    def min(col): return col.groupby(level=0).min()

    @op('max')
    def max(col): return col.groupby(level=0).max()

    @op('count')
    def nunique(col): return col.groupby(level=0).nunique()

    @op('lookup')
    def lookup(col: pd.Series, other: pd.Series):
        n = col.rename('key').to_frame()
        return n.join(other.rename('val'), on='key').val
    
    @op('filter')
    def filter(col: pd.Series, other: pd.Series):
        return col[col.index.isin(other[other].index)]


class Stack:
    index: pd.Index
    stack: list[Edge]
    errors: pd.Series

    def __init__(self, df: pd.DataFrame):
        self.edges = {
            col: Edge(df[col])
            for col in df.columns
        }
        self.index = df.index
        self.stack = []
        self.keep = pd.Series(True, index=self.index, dtype=bool)
        self.errors = pd.Series(index=self.index, dtype=str)
    
    @property
    def empty(self):
        """ Whether the stack has no current values """
        return len(self.stack) == 0

    def __len__(self):
        return len(self.stack)
    
    def dup(self):
        """ Duplicate the top value of the stack """
        assert not self.empty
        self.stack.append(self.stack[-1].dup())
        return self
    
    def pop(self):
        """ Pop the top column off of the stack """
        assert not self.empty
        return self.stack.pop()
    
    def top(self):
        """ Peek at the top value of the stack """
        assert not self.empty
        return self.stack[-1]
    
    def get(self, col: str):
        """ Normalize a column and push it onto the stack """
        assert col in self.edges
        self.stack.append(self.edges[col].dup())
        return self
    
    def filter(self):
        """ Pop filter column off of the stack and use to filter the second.
        the rows with a false value will be filtered out
        """
        # TODO: assert is bool type
        filter = self.pop()
        self.top().filter(filter)
        return self
    
    def assert_(self, error_type):
        """ Pop boolean column off of the stack
        the rows with a false value will be filtered out
        and get tagged with the error_type
        """
        # TODO: assert is bool type
        top = self.top()
        if not top.is_unique_index:
            self.all()
        is_valid = self.pop().col.reindex(self.index).fillna(True)
        self.keep &= is_valid
        self.errors.loc[~is_valid] = error_type
        return self
    
    def lookup(self, other: Edge):
        return self.top().lookup(other)

    def and_(self, val=None):
        val = val or self.pop()
        self.top() & val
        return self

    def or_(self, val=None):
        val = val or self.pop()
        self.top() | val
        return self
    
    def not_(self):
        ~self.top()
        return self

    def xor(self, val=None):
        val = val or self.pop()
        self.top() ^ val
        return self
    
    def eq(self, val=None):
        val = val or self.pop()
        self.top() == val
        return self
    
    def ne(self, val=None):
        val = val or self.pop()
        self.top() != val
        return self
    
    def lt(self, val=None):
        val = val or self.pop()
        self.top() < val
        return self
    
    def le(self, val=None):
        val = val or self.pop()
        self.top() <= val
        return self
    
    def gt(self, val=None):
        val = val or self.pop()
        self.top() > val
        return self
    
    def ge(self, val=None):
        val = val or self.pop()
        self.top() >= val
        return self
    
    def add(self, val=None):
        val = val or self.pop()
        self.top() + val
        return self
    
    def sub(self, val=None):
        val = val or self.pop()
        self.top() - val
        return self
    
    def mul(self, val=None):
        val = val or self.pop()
        self.top() * val
        return self
    
    def div(self, val=None):
        val = val or self.pop()
        self.top() / val
        return self
    
    def mod(self, val=None):
        val = val or self.pop()
        self.top() % val
        return self
    
    def all(self):
        self.top().all()
        return self

    def any(self):
        self.top().any()
        return self
    
    def sum(self):
        self.top().sum()
        return self
    
    def avg(self):
        self.top().avg()
        return self
    
    def min(self):
        self.top().min()
        return self
    
    def max(self):
        self.top().max()
        return self
    
    def cnt(self):
        top = self.top().nunique()
        top.col = top.col.reindex(self.index, fill_value=0)
        return self
    
    def __repr__(self):
        return repr(pd.DataFrame({
            **({
                i:edge.col if edge.is_unique_index else edge.col.groupby(level=0).unique()
                for i, edge in enumerate(self.stack)
            }),
            'keep': self.keep,
            'errors': self.errors,
        }, index=self.index))

# class Engine:
#     models: Models
#     stack: Stack

#     def __init__(self, models: Models):
#         self.models = models
    
#     def validate(self, model_ref: TYPE_REF, data: pd.DataFrame):
#         self.stack = Stack(data.index)
#         self.validate_model(data, self.models[model_ref])
    
#     def validate_edge(self, edge: Edge):
#         if not edge.multiple and not edge.nullable:
#             self.stack.dup().cnt().eq_const(1).assert_(f'count({edge.name}) == 1')
#         elif not edge.multiple:
#             self.stack.dup().cnt().le_const(1).assert_(f'count({edge.name}) <= 1')
#         elif not edge.nullable:
#             self.stack.dup().cnt().gt_const(0).assert_(f'count({edge.name}) > 0')

#     def validate_model(self, df: pd.DataFrame, model: Type):
#         assert model.has_index
#         assert isinstance(df, pd.DataFrame)
#         assert df.index.is_unique
#         if model.extends:
#             self.validate_model(df, model.extends)
#         for edge in model.own_edges:
#             if edge.name not in df.columns:
#                 continue
#             self.stack.load(df[edge.name])

def compute_expression(stack: Stack, expr: dict):
    assert len(expr) == 1
    op, args = list(expr.items())[0]
    args = [args] if not isinstance(args, list) else args
    constants = []
    for arg in args:
        if isinstance(arg, dict):
            compute_expression(stack, arg)
        else:
            constants.append(arg)
    if op in ('eq','ne','lt','le','gt','ge','add','sub','mul','div','mod'):
        assert len(args) <= 2
        assert len(constants) <= 1
        if len(constants) == 1:
            getattr(stack, f'{op}_const')(constants[0])
        else:
            assert len(args) == 2
            getattr(stack, op)()



if __name__ == "__main__":
    df = pd.DataFrame({
        # 'a': [[0,1], np.nan, [3], [1,2,8]],
        'a': [1, 2, 3, 4, np.nan],
        'b': [4, 1, 6, 7, np.nan],
    })
    l = Edge(pd.Series([['a1','a2'],'b','c','d'], name='l'))
    f = Edge(pd.Series([False, False, True, True], name='f'))

    # assertions = [
    #     { 'ge': 1 },
    #     { 'lt': 3 },
    # ]

    stack = Stack(df)


    # for i, expr in enumerate(assertions):
    #     stack.dup()
    #     compute_expression(stack, expr)
    #     stack.assert_(f'test{i+1}')
    # a = Edge(df.a)
    # b = a.dup() + 2
    # c = a.dup().filter(f)# + b
    # stack.dup().lookup(to_letter)
    stack.get('a').cnt().eq(1).assert_('count(a) == 1')
    print(stack)
    # stack.get('a').gt(1).assert_('a > 1')
    # stack.get('a').le(3).assert_('a <= 3')
    stack.get('a').get('b').lt().assert_('a < b')
    print(stack)
    print('hi')