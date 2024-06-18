from __future__ import annotations
import typing as t
import enum

import kye.parse.expressions as ast


class Operator(enum.Enum):
    SUB = '-'
    ADD = '+'
    MUL = '*'
    DIV = '/'
    MOD = '%'
    INV = "~"

    NOT = "!"
    NE = "!="
    EQ = "=="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    
    AND = "&"
    OR = "|"
    XOR = "^"
    
    IN = "in"
    IS = "is"
    
    @property
    def edge_name(self):
        return '$' + self.name.lower()
    
    @property
    def is_unary(self):
        return self in (Operator.INV, Operator.NOT)
    
    @property
    def is_mathematical(self):
        return self in (Operator.SUB, Operator.ADD, Operator.MUL, Operator.DIV, Operator.MOD)
    
    @property
    def is_comparison(self):
        return self in (Operator.EQ, Operator.NE, Operator.GT, Operator.GE, Operator.LT, Operator.LE)

class Expr:
    name: str
    args: t.Tuple[Expr, ...]

    def __init__(self, name: str, args: t.Iterable[Expr]):
        self.name = name
        self.args = tuple(args)
    
    def __repr__(self):
        return f"{self.name}({', '.join(repr(arg) for arg in self.args)})"

class Const(Expr):
    value: t.Any

    def __init__(self, value: t.Any):
        super().__init__('const', [])
        self.value = value

    def __repr__(self):
        return repr(self.value)

class Var(Expr):
    name: str

    def __init__(self, name: str):
        super().__init__('var', [])
        self.name = name

    def __repr__(self):
        return f"Var({self.name!r})"