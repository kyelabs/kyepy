from __future__ import annotations
import typing as t
from pathlib import Path
import lark

from kye.errors.compilation_errors import CompilationErrorReporter
import kye.parse.expressions as ast

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
    assert token.start_pos is not None and\
            token.end_pos is not None and\
            token.line is not None and\
            token.column is not None, 'propagate_positions is not enabled.'
    return ast.Token(
        type=token_type,
        lexeme=str(token),
        loc=ast.Location(
            start=token.start_pos,
            line=token.line,
            col=token.column,
            length=token.end_pos - token.start_pos,
        )
    )

class Transformer(lark.Transformer):
    def __init__(self, reporter: CompilationErrorReporter):
        self.__visit_tokens__ = True
        self.reporter = reporter

    def __default_token__(self, token: lark.Token):
        return parse_token(token)
    
    def __default__(self, data: t.Any, children: t.List[t.Any], meta: t.Dict[str, t.Any]):
        raise NotImplementedError(f'No handler for {data}({children})')

    @lark.v_args(inline=True)
    def _binary(self, value1, operator, value2):
        return ast.Binary(
            left = value1,
            operator = operator,
            right = value2,
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
    
    def statements(self, children: t.List[Ast]):
        return ast.Script(tuple(find_children(children, ast.Stmt)))

    def block(self, children: t.List[Ast]):
        return ast.Block(
            bracket=get_token(children, ast.TokenType.LEFT_BRACE),
            statements=tuple(find_children(children, ast.Stmt)),
        )
    
    def index(self, children: t.List[Ast]):
        return ast.Index(
            paren=get_token(children, ast.TokenType.LEFT_PAREN),
            names=tuple(find_tokens(children, ast.TokenType.EDGE)),
        )

    @lark.v_args(inline=True)
    def literal(self, token: ast.Token):
        value = None
        if token.type == ast.TokenType.NUMBER:
            value = float(token.lexeme)
        elif token.type == ast.TokenType.BOOLEAN:
            value = token.lexeme == 'TRUE'
        elif token.type == ast.TokenType.STRING:
            value = token.lexeme[1:-1]
        else:
            raise Exception(f'Unknown token type: {token.type}({token.lexeme})')
        return ast.Literal(
            token=token,
            value=value,
        )
    
    def model_def(self, children: t.List[Ast]):
        return ast.Model(
            name=get_token(children, ast.TokenType.TYPE),
            indexes=tuple(find_children(children, ast.Index)),
            body=get_child(children, ast.Block),
        )
    
    def type_def(self, children: t.List[Ast]):
        return ast.Type(
            name=get_token(children, ast.TokenType.TYPE),
            expr=get_child(children, ast.Expr),
        )
    
    def edge_def(self, children: t.List[Ast]):
        name = get_token(children, ast.TokenType.EDGE)
        title = find_token(children, ast.TokenType.STRING)
        if title is not None:
            title = title.lexeme[1:-1]
        # TODO: make sure we are inside of a select statement
        if len(children) == 1:
            block = ast.EdgeIdentifier(name)
        else:
            block = get_child(children, ast.Block, ast.Expr)
        cardinality = find_token(children, ast.TokenType.STAR, ast.TokenType.PLUS, ast.TokenType.QUESTION, ast.TokenType.NOT)
        if cardinality is None:
            cardinality = ast.Cardinality.ONE
        else:
            cardinality = ast.Cardinality(cardinality.lexeme)
        if isinstance(block, ast.Block):
            raise NotImplementedError('Block not implemented.')
        return ast.Edge(
            name=name,
            title=title,
            params=tuple(find_children(children, ast.Index)),
            cardinality=cardinality,
            expr=block
        )

    def assert_stmt(self, children: t.List[Ast]):
        return ast.Assert(
            keyword=get_token(children, ast.TokenType.ASSERT),
            expr=get_child(children, ast.Expr)
        )
    
    def type_identifier(self, children: t.List[Ast]):
        return ast.TypeIdentifier(
            name=get_token(children, ast.TokenType.TYPE),
            format=find_token(children, ast.TokenType.FORMAT),
        )
    
    def edge_identifier(self, children: t.List[Ast]):
        edge = get_token(children, ast.TokenType.EDGE)
        if edge.lexeme == 'this':
            return ast.This(keyword=edge)
        return ast.EdgeIdentifier(
            name=edge
        )
    
    def filter_exp(self, children: t.List[Ast]):
        (object, *arguments) = find_children(children, ast.Expr)
        return ast.Filter(
            object=object,
            bracket=get_token(children, ast.TokenType.LEFT_SQUARE),
            conditions=tuple(arguments),
        )

    def call_exp(self, children: t.List[Ast]):
        (callee, *arguments) = find_children(children, ast.Expr)
        return ast.Call(
            object=callee,
            paren=get_token(children, ast.TokenType.LEFT_PAREN),
            arguments=tuple(arguments),
        )
    
    def select_exp(self, children: t.List[Ast]):
        return ast.Select(
            object=get_child(children, ast.Expr),
            body=get_child(children, ast.Block),
        )
    
    def dot_exp(self, children: t.List[Ast]):
        return ast.Get(
            object=get_child(children, ast.Expr),
            dot=get_token(children, ast.TokenType.DOT),
            name=get_token(children, ast.TokenType.EDGE),
        )


GRAMMAR = (Path(__file__).parent / 'grammar.lark').read_text()

class Parser:
    def __init__(self, reporter: CompilationErrorReporter):
        self.reporter = reporter
        self.transformer = Transformer(reporter)
        self.definitions_parser = self.get_parser('statements')
        self.expressions_parser = self.get_parser('exp')

    def get_parser(self, start):
        return lark.Lark(
            GRAMMAR,
            parser='lalr',
            propagate_positions=True,
            keep_all_tokens=True,
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
            return ast.Script(tuple())
        return self.transformer.transform(tree)

    def parse_expression(self, source: str) -> t.Optional[ast.Expr]:
        try:
            tree = self.expressions_parser.parse(source, on_error=self.on_error)
        except lark.exceptions.UnexpectedInput as e:
            return None
        return self.transformer.transform(tree)

__all__ = ['Parser']