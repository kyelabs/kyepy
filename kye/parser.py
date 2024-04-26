from __future__ import annotations
import typing as t
from pathlib import Path
from enum import Enum
import lark
from kye.errors import ErrorReporter
import kye.expressions as ast

Ast = t.Union[ast.Node, ast.Token]

T = t.TypeVar("T")

def find_children(nodes: t.List[Ast], *type: t.Type[T]) -> t.List[T]:
    return [
        node for node in nodes
        if isinstance(node, type)
    ]

def find_tokens(nodes: t.List[Ast], *type: ast.TokenType) -> t.List[ast.Token]:
    return [
        node for node in nodes
        if isinstance(node, ast.Token) and node.type in type
    ]

def find_child(nodes: t.List[Ast], *type: t.Type[T]) -> t.Optional[T]:
    for child in find_children(nodes, *type):
        return child
    return None

def find_token(nodes: t.List[Ast], *type: ast.TokenType) -> t.Optional[ast.Token]:
    for child in find_tokens(nodes, *type):
        return child
    return None

def get_child(nodes: t.List[Ast], *type: t.Type[T]) -> T:
    child = find_child(nodes, *type)
    if child is None:
        raise ValueError(f'Token {type} not found.')
    return child

def get_token(nodes: t.List[Ast], type: ast.TokenType) -> ast.Token:
    token = find_token(nodes, type)
    if token is None:
        raise ValueError(f'Token {type} not found.')
    return token

def parse_token(token: lark.Token):
    token_type = None
    if token.type in ('NUMBER', 'STRING', 'BOOLEAN', 'FORMAT', 'EDGE', 'TYPE'):
        token_type = ast.TokenType(token.type)
    else:
        token_type = ast.TokenType(token)
    return ast.Token(token_type, str(token), token.pos_in_stream)

class Transformer(lark.Transformer):
    def __init__(self, reporter: ErrorReporter):
        self.__visit_tokens__ = True
        self.reporter = reporter

    def __default_token__(self, token: lark.Token):
        return parse_token(token)
    
    def __default__(self, data: t.Any, children: t.List[t.Any], meta: t.Dict[str, t.Any]):
        raise NotImplementedError(f'No handler for {data}({children})')

    @lark.v_args(inline=True)
    def _binary(self, value1, operator, value2):
        return ast.Binary(
            value1,
            operator,
            value2,
        )
    
    def _list(self, node):
        return list(node)

    add_exp = _binary
    mult_exp = _binary
    comp_exp = _binary
    and_exp = _binary
    xor_exp = _binary
    or_exp = _binary
    is_exp = _binary
    
    def statements(self, children: t.List[ast.Stmt]):
        return ast.Script(children)

    def block(self, children: t.List[ast.Stmt]):
        return ast.Block(children)
    
    def index(self, children: t.List[ast.Token]):
        return ast.Index(children)

    @lark.v_args(inline=True)
    def literal(self, val: ast.Token):
        if val.type == ast.TokenType.NUMBER:
            return ast.Literal(float(val.lexeme))
        if val.type == ast.TokenType.BOOLEAN:
            return ast.Literal(val.lexeme == 'TRUE')
        if val.type == ast.TokenType.STRING:
            return ast.Literal(val.lexeme[1:-1])
        raise Exception(f'Unknown token type: {val.type}({val.lexeme})')
    
    def model_def(self, children: t.List[Ast]):
        name = get_token(children, ast.TokenType.TYPE)
        indexes = find_children(children, ast.Index)
        block = get_child(children, ast.Block)
        return ast.Model(name, indexes, block)
    
    def type_def(self, children: t.List[Ast]):
        name = get_token(children, ast.TokenType.TYPE)
        parent = get_child(children, ast.Expr)
        body = find_child(children, ast.Block)
        if body is None:
            body = ast.Block([])
        return ast.Type(name, parent, body)
    
    def edge_def(self, children: t.List[Ast]):
        name = get_token(children, ast.TokenType.EDGE)
        indexes = find_children(children, ast.Index)
        block = get_child(children, ast.Block, ast.Expr)
        cardinality = find_token(children, ast.TokenType.STAR, ast.TokenType.PLUS, ast.TokenType.QUESTION, ast.TokenType.NOT)
        if cardinality is None:
            cardinality = ast.Token(ast.TokenType.NOT, '!', -1)
        # if isinstance(block, ast.Expr):
        #     block = ast.Block([
        #         ast.Return(
        #             ast.Token(ast.TokenType.RETURN, 'return', -1),
        #             block
        #         )
        #     ])
        if isinstance(block, ast.Block):
            raise NotImplementedError('Block not implemented.')
        return ast.Edge(name, indexes, cardinality, block)

    def assert_stmt(self, children: t.List[Ast]):
        keyword = get_token(children, ast.TokenType.ASSERT)
        value = get_child(children, ast.Expr)
        return ast.Assert(keyword, value)
    
    def return_stmt(self, children: t.List[Ast]):
        keyword = get_token(children, ast.TokenType.RETURN)
        value = get_child(children, ast.Expr)
        return ast.Return(keyword, value)
    
    def type_identifier(self, children: t.List[Ast]):
        return ast.TypeIdentifier(
            get_token(children, ast.TokenType.TYPE),
            find_token(children, ast.TokenType.FORMAT),
        )
    
    def edge_identifier(self, children: t.List[Ast]):
        edge = get_token(children, ast.TokenType.EDGE)
        if edge.lexeme == 'this':
            return ast.This(edge)
        return ast.EdgeIdentifier(edge)
    
    def filter_exp(self, children: t.List[Ast]):
        (object, *arguments) = find_children(children, ast.Expr)
        return ast.Filter(
            object,
            arguments,
        )

    def call_exp(self, children: t.List[Ast]):
        (callee, *arguments) = find_children(children, ast.Expr)
        return ast.Call(callee, arguments)
    
    def dot_exp(self, children: t.List[Ast]):
        object = get_child(children, ast.Expr)
        name = get_token(children, ast.TokenType.EDGE)
        return ast.Get(object, name)


GRAMMAR = (Path(__file__).parent / 'grammar.lark').read_text()

class Parser:
    def __init__(self, reporter: ErrorReporter):
        self.reporter = reporter
        self.transformer = Transformer(reporter)
        self.definitions_parser = self.get_parser('statements')
        self.expressions_parser = self.get_parser('exp')

    def get_parser(self, start):
        return lark.Lark(
            GRAMMAR,
            parser='lalr',
            propagate_positions=True,
            start=start,
        )
    
    def on_error(self, e: lark.exceptions.UnexpectedInput) -> bool:
        if isinstance(e, lark.exceptions.UnexpectedCharacters):
            self.reporter.unexpected_character_error(e.pos_in_stream)
        if isinstance(e, lark.exceptions.UnexpectedToken):
            token = t.cast(lark.Token, e.__dict__['token'])
            if token.type == '$END':
                self.reporter.unterminated_token_error("Unexpected end of file.")
            else:
                token = parse_token(token)
                self.reporter.parser_error(token, "Unexpected token")
        if isinstance(e, lark.exceptions.UnexpectedEOF):
            self.reporter.unterminated_token_error("Unexpected end of file.")
        return False
    
    def parse_definitions(self, source: str) -> ast.Script:
        try:
            tree = self.definitions_parser.parse(source, on_error=self.on_error)
        except lark.exceptions.UnexpectedInput as e:
            return ast.Script([])
        return self.transformer.transform(tree)

    def parse_expression(self, source: str) -> ast.Expr:
        try:
            tree = self.expressions_parser.parse(source, on_error=self.on_error)
        except lark.exceptions.UnexpectedInput as e:
            return ast.Literal(None)
        return self.transformer.transform(tree)

__all__ = ['Parser']