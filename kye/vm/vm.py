import yaml
from pathlib import Path
from enum import Enum, auto
import pandas as pd
import numpy as np

class OP(Enum):
    GET_COLUMN = auto(), 0, 'str'
    LT_CONST =   auto(), 1, 'any'
    EQ_CONST =   auto(), 1, 'any'
    NUNIQUE =    auto(), 1
    
    @property
    def code(self):
        return self.value[0]
    
    @property
    def pops(self):
        return self.value[1]
    
    @property
    def signature(self):
        return self.value[2:]
    
    @property
    def arity(self):
        return len(self.signature)
    
    def matches_signature(self, args):
        if len(args) != len(self.signature):
            return False
        for arg, sig_arg in zip(args, self.signature):
            if sig_arg == 'any':
                if not isinstance(arg, (int, float, str)):
                    return False
            elif sig_arg == 'num':
                if not isinstance(arg, (int, float)):
                    return False
            elif sig_arg == 'str':
                if not isinstance(arg, str):
                    return False
            else:
                raise ValueError(f'Invalid signature: {sig_arg}')
        return True

BASE_DIR = Path(__file__).resolve().parent
commands = yaml.safe_load((BASE_DIR / 'example.yaml').read_text())

def parse_command(cmd) -> tuple[OP, tuple]:
    op = None
    args = None
    if isinstance(cmd, str):
        op = OP[cmd.upper()]
        assert op.arity == 0
        args = tuple()
    elif isinstance(cmd, dict):
        assert len(cmd) == 1
        cmd, args = list(cmd.items())[0]
        assert isinstance(cmd, str)
        if isinstance(args, list):
            args = tuple(args)
        else:
            assert isinstance(args, (str, int, float))
            args = (args,)
        op = OP[cmd.upper()]
    else:
        raise ValueError(f'Invalid command: {cmd}')
    assert op.matches_signature(args)
    return op, args

class Stack:
    def __init__(self):
        self.stack = pd.DataFrame()
        self.stack_size = 0
    
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
        return col
    
    def pop_agg(self):
        return self.pop().groupby(self.stack.index)

stack = Stack()
df = pd.DataFrame({
    'id': [1, 2,     3],
    'a':  [1, 1,     2],
    'b':  [4, [5,6], 7],
}).set_index('id', drop=False)

def get_column(col_name):
    assert col_name in df
    return df[col_name].explode().dropna().infer_objects()

for cmd in commands:
    cmd, args = parse_command(cmd)
    print(cmd, args)
    if cmd == OP.GET_COLUMN:
        stack.push(get_column(args[0]))
    elif cmd == OP.LT_CONST:
        stack.push(stack.pop() < args[0])
    elif cmd == OP.EQ_CONST:
        stack.push(stack.pop() == args[0])
    elif cmd == OP.NUNIQUE:
        stack.push(stack.pop_agg().nunique())
    print(stack.stack)
    # op, args = cmd['op'], cmd['args']
    # print(op, args)
    # op, args = OP(op), args
    # print(op, args)
    # assert isinstance(op, OP)
    # assert isinstance(args, op.value[1])