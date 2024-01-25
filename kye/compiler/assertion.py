from typing import Any, Literal, Union

LiteralType = Union[float,str,bool]

ASSERTION_CLASSES = []

class Assertion:
    """ Abstract Class for assertion operations """
    OPERATORS: tuple[str]
    op: str
    arg: Any

    def __init__(self, op, arg):
        assert self.allows_operator(op)
        self.op = op
        self.arg = arg
    
    def __repr__(self):
        return f'{self.op}({repr(self.arg)})'

    @classmethod
    def allows_operator(cls, operator):
        assert hasattr(cls, 'OPERATORS')
        return operator in cls.OPERATORS
    
    def __init_subclass__(cls) -> None:
        assert hasattr(cls, 'OPERATORS')
        ASSERTION_CLASSES.append(cls)

class TypeAssertion(Assertion):
    OPERATORS = ('type')
    arg: Literal['string','number','boolean']

    def __init__(self, op, arg):
        assert arg in ('string','number','boolean')
        super().__init__('type',arg)

class EquivalenceAssertion(Assertion):
    OPERATORS = ('eq','ne')
    arg: list[LiteralType]

    def __init__(self, op, arg):
        if type(arg) is not list:
            arg = [arg]
        super().__init__(op, arg)

class RangeAssertion(Assertion):
    OPERATORS = ('gt', 'gte', 'lt', 'lte')
    arg: float
    
    def __init__(self, op, arg):
        assert isinstance(arg, (int, float))
        super().__init__(op, arg)

def assertion_factory(op, arg):    
    for cls in ASSERTION_CLASSES:
        if cls.allows_operator(op):
            return cls(op, arg)
    raise ValueError(f'Unknown operator {op}')