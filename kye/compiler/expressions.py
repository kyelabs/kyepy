from __future__ import annotations
from functools import cached_property
import kye.compiler.models as m
import typing as t

EXPRESSIONS: dict[str, Expression] = {}

Literal = t.Union[int, float, str, bool]
ExpOrLiteral = t.Union[Literal, tuple[str, list]]
Exp = tuple[str, list[ExpOrLiteral]]
Signature = tuple[list[str], str]

def pop_items(items, i):
    if i == 0:
        return items, []
    return items[:-i], items[-i:]


class Expression:
    name = 'expression'
    num_expected_args = 2
    _arg_types: t.Optional[list[m.Type]] = None
    _type: t.Optional[m.Type] = None

    def __init__(self, *args: Expression):
        assert len(args) <= self.num_expected_args
        self.args = args

    def __init_subclass__(cls) -> None:
        cls.name = cls.__name__.lower()
        EXPRESSIONS[cls.name] = cls
    
    def __iter__(self):
        for arg in self.args:
            yield from arg
        yield self
    
    def set_arg_types(self, arg_types: list[m.Type]):
        assert len(arg_types) == self.num_needed_args
        self._arg_types = []
        for arg in self.args:
            arg_types, give = pop_items(arg_types, arg.num_needed_args)
            arg.set_arg_types(give)
            self._arg_types.append(arg.type)
        self._arg_types = arg_types + self._arg_types

    @property
    def type(self) -> m.Type:
        if isinstance(self, Get):
            assert self.args[-1].is_string
            return self._arg_types[0][self.args[-1].val].type
        return self._type or self._arg_types[0]
    
    @property
    def is_string(self):
        return isinstance(self, Const) and type(self.val) is str
    
    @cached_property
    def num_needed_args(self):
        n = 0
        for arg in self.args:
            n += arg.num_needed_args
        n += self.num_expected_args - len(self.args)
        return n
    
    def __repr__(self):
        return '({} {})'.format(
            self.name, 
            ' '.join(repr(arg) for arg in self.args)
        )

class Const(Expression):
    num_expected_args = 0
    val: Literal
    def __init__(self, val):
        super().__init__()
        self.val = val
        if isinstance(val, str):
            self._type = m.String
        elif isinstance(val, (int, float)):
            self._type = m.Number
        elif isinstance(val, bool):
            self._type = m.Boolean
        else:
            raise Exception('Unknown value type')
    
    def __repr__(self):
        return repr(self.val)

class Filter(Expression):
    pass

class Assert(Expression):
    pass

class Get(Expression):
    def get_type(self):
        self.args

class Identity(Expression):
    """ Operations that require being able to differentiate values """
    _type = m.Boolean

class Eq(Expression):
    pass

class Ne(Expression):
    pass

class Ordinal(Expression):
    """ Operations that require values to have an order """
    _type = m.Boolean

class Lt(Ordinal):
    pass

class Gt(Ordinal):
    pass

class Le(Identity, Ordinal):
    pass

class Ge(Identity, Ordinal):
    pass

class Interval(Expression):
    """ Operations that require it to be possible to
    calculate distances between numbers
    (addition and subtraction) """

class Add(Interval):
    pass

class Sub(Interval):
    pass

class Scalar(Expression):
    """ Operations that require values to be a distance from absolute zero
    (multiplication and division) """
    pass

class Mul(Scalar):
    pass

class Div(Scalar):
    pass

class Mod(Scalar):
    pass

class Logical(Expression):
    """ Operations that require a falsy state """
    _type = m.Boolean

class And(Logical):
    pass

class Or(Logical):
    pass

class Not(Logical):
    num_expected_args = 1

class Xor(Logical):
    pass

class Aggregation(Expression):
    """ Operations that produce a single value
    from many values """
    num_expected_args = 1

class Count(Identity, Aggregation):
    pass

class All(Logical, Aggregation):
    pass

class Any(Logical, Aggregation):
    pass

class Min(Ordinal, Aggregation):
    pass

class Max(Ordinal, Aggregation):
    pass

class Sum(Scalar, Aggregation):
    pass

class Avg(Scalar, Aggregation):
    pass

def normalize_args(src: t.Union[Literal, dict]) -> ExpOrLiteral:
    if type(src) is not dict:
        return src
    assert len(src) == 1
    op, args = list(src.items())[0]
    args = [args] if not isinstance(args, list) else args
    return op, [normalize_args(arg) for arg in args]

def normalize_pipes(src: ExpOrLiteral) -> ExpOrLiteral:
    if type(src) is not tuple:
        return src
    op, args = src
    if op != 'pipe':
        return op, args
    
    assert len(args) > 0, 'expected pipe to have at least one item'
    out = args[0]
    for arg in args[1:]:
        assert type(arg) is tuple, 'expected no literal arguments to pipe operation'
        op, args = arg
        out = (op, [out, *args])
    return out

def transform(src: ExpOrLiteral):
    if type(src) is not tuple:
        return Const(src)
    op, args = src
    assert op in EXPRESSIONS, f'Unknown function {op}'
    return EXPRESSIONS[op](*(
        transform(arg)
        for arg in args
    ))

def compile_expression(src: ExpOrLiteral) -> Expression:
    src = normalize_args(src)
    src = normalize_pipes(src)
    exp = transform(src)
    return exp
