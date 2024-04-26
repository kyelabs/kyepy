from __future__ import annotations
from dataclasses import dataclass
import typing as t
import enum
import re

def snake_case(s):
  return re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower()

class Visitor:
    def visit_children(self, node: Node):
        for child in node.__dict__.values():
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, Node):
                        self.visit(item)
            if isinstance(child, Node):
                self.visit(child)
    
    def visit(self, node: Node) -> t.Any:
        node_class = snake_case(node.__class__.__name__)
        visit_method = getattr(self, f'visit_{node_class}', self.visit_children)
        return visit_method(node)

class Cardinality(enum.Enum):
    ONE = '!'
    MANY = '*'
    MAYBE = '?'
    MORE = '+'

class TokenType(enum.Enum):
    # Single-character tokens.
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    LEFT_BRACE = "{"
    RIGHT_BRACE = "}"
    COMMA = ","
    DOT = "."
    MINUS = "-"
    PLUS = "+"
    SLASH = "/"
    STAR = "*"
    COLON = ":"
    QUESTION = "?"
    AND = "&"
    OR = "|"

    # One or two character tokens.
    NOT = "!"
    NE = "!="
    ASSIGN = "="
    EQ = "=="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="

    # Literals.
    TYPE = "TYPE"
    FORMAT = "FORMAT"
    EDGE = "EDGE"
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"

    # Keywords.
    NULL = "null"
    IF = "if"
    ELSE = "else"
    RETURN = "return"
    SUPER = "super"
    THIS = "this"
    ASSERT = "assert"


class Token:
    type: TokenType
    lexeme: str
    start: int

    def __init__(self, token_type: TokenType, lexeme: str, pos: int):
        self.type = token_type
        self.lexeme = lexeme
        self.start = pos
    
    def __str__(self):
        return self.lexeme
    
    def __repr__(self):
        return f"{self.type.name}({self.lexeme})"
    
    @property
    def end(self):
        return self.start + len(self.lexeme)

class Node:
    pass

class Stmt(Node):
    pass

class Expr(Node):
    pass

@dataclass
class Index(Node):
    names: t.List[Token]

@dataclass
class Block(Node):
    statements: t.List[Stmt]

@dataclass
class Script(Node):
    statements: t.List[Stmt]

@dataclass
class Model(Stmt):
    name: Token
    indexes: t.List[Index]
    body: Block

@dataclass
class Type(Stmt):
    name: Token
    parent: Expr
    body: Block

@dataclass
class Edge(Stmt):
    name: Token
    params: t.List[Index]
    cardinality: Token
    body: Expr

@dataclass
class Assert(Stmt):
    keyword: Token
    value: Expr

@dataclass
class Return(Stmt):
    keyword: Token
    value: Expr

@dataclass
class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr

@dataclass
class Unary(Expr):
    operator: Token
    right: Expr

@dataclass
class Literal(Expr):
    value: t.Any

@dataclass
class TypeIdentifier(Expr):
    name: Token
    format: t.Optional[Token]

@dataclass
class EdgeIdentifier(Expr):
    name: Token

@dataclass
class Call(Expr):
    callee: Expr
    arguments: t.List[Expr]

@dataclass
class Get(Expr):
    object: Expr
    name: Token

@dataclass
class Filter(Expr):
    object: Expr
    conditions: t.List[Expr]

@dataclass
class This(Expr):
    keyword: Token