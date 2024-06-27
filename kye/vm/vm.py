import pandas as pd
import numpy as np

from op import OP, parse_command

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
        if not col.index.is_unique:
            # Not sure which is faster
            # col = col.groupby(col.index).unique().explode()
            col = col.reset_index().drop_duplicates().set_index(col.index.names).iloc[:,0]
        return col
    
    def push(self, val: pd.Series):
        val = self._preprocess(val)
        if self.is_empty:
            self.stack = val.rename(self.stack_size).to_frame()
        else:
            self.stack = pd.merge(self.stack, val.rename(self.stack_size), left_index=True, right_index=True, how='outer')
        self.stack_size += 1
    
    def pop(self) -> pd.Series:
        self.stack_size -= 1
        col = self.stack.loc[:,self.stack_size]
        self.stack.drop(columns=[self.stack_size], inplace=True)
        return self._preprocess(col)


df = pd.DataFrame({
    'id': [1, 2,     3],
    'a':  [1, 1,     2],
    'b':  [4, [5,6], 7],
}).set_index('id', drop=False)

def get_column(col_name):
    assert col_name in df
    return df[col_name].explode().dropna().infer_objects()

def groupby_index(col):
    return col.groupby(col.index)

def run_command(op, args):
    if op == OP.COL:
        return get_column(args[0])
    elif op == OP.IS_NULL:
        return args[0].isnull()
    elif op == OP.NOT_NULL:
        return args[0].notnull()
    elif op == OP.NOT:
        return ~args[0]
    elif op == OP.NEG:
        return -args[0]
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
    elif op == OP.COUNT:
        return groupby_index(args[0]).nunique()
    else:
        raise ValueError(f'Invalid operation: {op}')

def run(commands):
    stack = Stack()
    
    for cmd in commands:
        cmd, args = parse_command(cmd)
        print(cmd, args)
        num_stack_args = cmd.arity - len(args)
        assert len(stack) >= num_stack_args
        for _ in range(num_stack_args):
            args.insert(0, stack.pop())
        result = run_command(cmd, args)
        stack.push(result)
        print(stack.stack)


if __name__ == '__main__':
    from pathlib import Path
    import yaml
    BASE_DIR = Path(__file__).resolve().parent
    run(yaml.safe_load('''
        - col: a
        - col: b
        - add: True
    '''))