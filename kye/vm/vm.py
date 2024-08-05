from __future__ import annotations
import typing as t
import pandas as pd
import numpy as np

from kye.vm.op import OP
from kye.compiled import Cmd

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
    df: pd.DataFrame
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        
    def get_column(self, col_name):
        if col_name in self.df:
            return self.df[col_name].explode().dropna().infer_objects()
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
        elif op == OP.LE:
            return args[0] <= args[1]
        elif op == OP.GE:
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

    def eval(self, commands: t.List[Cmd]):
        stack = Stack()
        
        for cmd in commands:
            args = cmd.args[:]
            assert len(stack) >= cmd.num_stack_args
            for _ in range(cmd.num_stack_args):
                args.insert(0, stack.pop())
            result = self.run_command(cmd.op, args)
            stack.push(result)
        
        return stack.pop()
