import duckdb
from kyepy.kye_ast import *

def validate_duckdb(ast, con):
    if isinstance(ast, Model):
        pass