from __future__ import annotations
from dataclasses import dataclass
import typing as t
import enum
import re

def snake_case(s):
  return re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower()

class Visitor:
    # Script & Block are pretty boring, so we'll add default
    # implementations for them here.
    def visit_script(self, script_ast: Script):
        for statement in script_ast.statements:
            self.visit(statement)

    def visit_block(self, block_ast: Block):
        for statement in block_ast.statements:
            self.visit(statement)

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
        visit_method = getattr(self, f'visit_{node_class}', None)
        value = None
        if visit_method is None:
            print(f"WARN: visit_{node_class} not implemented on {self.__class__.__name__}")
            self.visit_children(node)
        else:
            value = visit_method(node)
        
        # check for after methods
        for parent in node.__class__.__mro__:
            if not issubclass(parent, Node):
                break
            parent_class = snake_case(parent.__name__)
            after_listener = getattr(self, f'after_{parent_class}', None)
            if after_listener is not None:
                value = after_listener(node, value)
        
        return value

class Cardinality(enum.Enum):
    ONE = '!'
    MANY = '*'
    MAYBE = '?'
    MORE = '+'
    
    @property
    def allows_null(self):
        return self in (Cardinality.MAYBE, Cardinality.MANY)
    
    @property
    def allows_many(self):
        return self in (Cardinality.MORE, Cardinality.MANY)

class TokenType(enum.Enum):
    # Single-character tokens.
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    LSQUARE = "["
    RSQUARE = "]"
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
    REGEX = "REGEX"

    # Keywords.
    NULL = "null"
    IF = "if"
    ELSE = "else"
    SUPER = "super"
    THIS = "this"
    ASSERT = "assert"
    
    @property
    def is_mathematical(self):
        return self in (TokenType.MINUS, TokenType.PLUS, TokenType.SLASH, TokenType.STAR)
    
    @property
    def is_comparison(self):
        return self in (TokenType.EQ, TokenType.NE, TokenType.GT, TokenType.GE, TokenType.LT, TokenType.LE)
    
    @property
    def is_logical(self) -> bool:
        return self in (TokenType.AND, TokenType.OR, TokenType.NOT)

@dataclass(eq=True, frozen=True, slots=True)
class Location:
    start: int
    line: int
    col: int
    length: int
    
    def __str__(self):
        return f"{self.line}:{self.col}"

    @property
    def end(self):
        return self.start + self.length

NULL_LOCATION = Location(-1, -1, -1, 0)

@dataclass
class Token:
    type: TokenType
    lexeme: str
    loc: Location
    
    def __str__(self):
        return self.lexeme
    
    def __repr__(self):
        return f"{self.type.name}({self.lexeme})"

class Node:
    pass

class Stmt(Node):
    pass

class Expr(Node):
    pass

@dataclass
class Index(Node):
    paren: Token
    names: t.Tuple[Token, ...]

@dataclass
class Block(Node):
    bracket: Token
    statements: t.Tuple[Stmt, ...]

@dataclass
class Script(Node):
    statements: t.Tuple[Stmt, ...]

@dataclass
class Model(Stmt):
    name: Token
    indexes: t.Tuple[Index, ...]
    body: Block

@dataclass
class Type(Stmt):
    name: Token
    expr: Expr

@dataclass
class Edge(Stmt):
    name: Token
    title: t.Optional[str]
    params: t.Tuple[Index, ...]
    cardinality: Cardinality
    expr: Expr

@dataclass
class Assert(Stmt):
    keyword: Token
    expr: Expr

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
    token: Token
    value: t.Any
    
    @property
    def type(self):
        if self.token.type == TokenType.STRING:
            return 'String'
        if self.token.type == TokenType.NUMBER:
            return 'Number'
        if self.token.type == TokenType.BOOLEAN:
            return 'Boolean'
        raise ValueError(f"Unknown literal type: {self.token.type}")

@dataclass
class Regex(Expr):
    token: Token
    pattern: str

@dataclass
class TypeIdentifier(Expr):
    name: Token
    format: t.Optional[Token]

@dataclass
class EdgeIdentifier(Expr):
    name: Token

@dataclass
class Call(Expr):
    object: Expr
    paren: Token
    arguments: t.Tuple[Expr, ...]

@dataclass
class Get(Expr):
    object: Expr
    dot: Token
    name: Token

@dataclass
class Filter(Expr):
    object: Expr
    bracket: Token
    conditions: t.Tuple[Expr, ...]

@dataclass
class Select(Expr):
    object: Expr
    body: Block

@dataclass
class This(Expr):
    keyword: Token