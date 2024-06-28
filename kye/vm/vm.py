from __future__ import annotations
import typing as t
import pandas as pd
import numpy as np

from kye.vm.op import OP, parse_command
from kye.load.loader import Loader

class Stack:
    def __init__(self):
        self.stack = pd.DataFrame()
        self.stack_size = 0
    
    def __len__(self):
        return self.stack_size
    
    @property
    def is_empty(self):
        return self.stack_size == 0

    def _preprocess(self, col: pd.Series) -> pd.Series:
        if col.hasnans:
            col = col.dropna()
        # Duplicate index values are only allowed if they each have a different value
        if not col.index.is_unique:
            # Not sure which is faster
            # col = col.groupby(col.index).unique().explode()
            col = col.reset_index().drop_duplicates().set_index(col.index.names).iloc[:,0] # type: ignore
        return col
    
    def push(self, val: pd.Series):
        val = self._preprocess(val)
        if self.is_empty:
            self.stack = val.rename(self.stack_size).to_frame()
        else:
            self.stack = pd.merge(self.stack, val.rename(self.stack_size), left_index=True, right_index=True, how='outer')
        self.stack_size += 1
    
    def pop(self) -> pd.Series:
        assert not self.is_empty
        self.stack_size -= 1
        col = self.stack.loc[:,self.stack_size]
        self.stack.drop(columns=[self.stack_size], inplace=True)
        return self._preprocess(col)


def groupby_index(col):
    return col.groupby(col.index)

class VM:
    tables: t.Dict[str, pd.DataFrame]
    this: t.Optional[str]
    
    def __init__(self, loader: Loader):
        self.loader = loader
        self.tables = {}
        self.this = None
    
    def load_table(self, table: str):
        if table not in self.tables:
            self.tables[table] = self.loader.load(table).to_pandas()
        return self.tables[table]
    
    def get_column(self, col_name):
        assert self.this is not None
        df = self.load_table(self.this)
        if col_name in df:
            return df[col_name].explode().dropna().infer_objects()
        expr = self.loader.get_source(self.this)[col_name].expr
        if expr is not None:
            return self.eval(expr)
        raise ValueError(f'Column not found: {col_name}')

    def run_command(self, op, args):
        if op == OP.COL:
            return self.get_column(args[0])
        elif op == OP.STR:
            return args[0].astype(str)
        elif op == OP.NA:
            return args[0].isnull()
        elif op == OP.DEF:
            return args[0].notnull()
        elif op == OP.NOT:
            return ~args[0]
        elif op == OP.NEG:
            return -args[0]
        elif op == OP.LEN:
            return args[0].str.len()
        elif op == OP.NE:
            return args[0] != args[1]
        elif op == OP.EQ:
            return args[0] == args[1]
        elif op == OP.OR:
            return args[0] | args[1]
        elif op == OP.AND:
            return args[0] & args[1]
        elif op == OP.LT:
            return args[0] < args[1]
        elif op == OP.GT:
            return args[0] > args[1]
        elif op == OP.LTE:
            return args[0] <= args[1]
        elif op == OP.GTE:
            return args[0] >= args[1]
        elif op == OP.ADD:
            return args[0] + args[1]
        elif op == OP.SUB:
            return args[0] - args[1]
        elif op == OP.MUL:
            return args[0] * args[1]
        elif op == OP.DIV:
            return args[0] / args[1]
        elif op == OP.MOD:
            return args[0] % args[1]
        elif op == OP.CONCAT:
            return args[0] + args[1]
        elif op == OP.COUNT:
            return groupby_index(args[0]).nunique()
        else:
            raise ValueError(f'Invalid operation: {op}')

    def eval(self, commands):
        stack = Stack()
        
        for cmd, args in commands:
            num_stack_args = cmd.arity - len(args)
            assert len(stack) >= num_stack_args
            for _ in range(num_stack_args):
                args.insert(0, stack.pop())
            result = self.run_command(cmd, args)
            stack.push(result)
        
        return stack.pop()

    def validate(self, table: str):
        self.this = table
        source = self.loader.get_source(table)
        for assertion in source.assertions:
            result = self.eval(assertion.expr)
            if not result.all():
                print('Assertion failed:', assertion.msg)
                print(self.load_table(table)[~result])
        self.this = None
        return True