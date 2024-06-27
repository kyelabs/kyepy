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
        return col


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

def run(commands):
    stack = Stack()
    
    for cmd in commands:
        cmd, const_args = parse_command(cmd)
        assert len(stack) >= cmd.num_stack_args
        # reverse the order of the stack arguments
        stack_args = [stack.pop() for _ in range(cmd.num_stack_args)][::-1]
        print(cmd, const_args)
        if cmd == OP.LOAD_COL:
            stack.push(get_column(const_args[0]))
        elif cmd == OP.IS_NULL:
            stack.push(stack_args[0].isnull())
        elif cmd == OP.NOT_NULL:
            stack.push(stack_args[0].notnull())
        elif cmd == OP.NOT:
            stack.push(~stack_args[0])
        elif cmd == OP.NEG:
            stack.push(-stack_args[0])
        elif cmd == OP.NE:
            stack.push(stack_args[0] != stack_args[1])
        elif cmd == OP.EQ:
            stack.push(stack_args[0] == stack_args[1])
        elif cmd == OP.OR:
            stack.push(stack_args[0] | stack_args[1])
        elif cmd == OP.AND:
            stack.push(stack_args[0] & stack_args[1])
        elif cmd == OP.LT:
            stack.push(stack_args[0] < stack_args[1])
        elif cmd == OP.GT:
            stack.push(stack_args[0] > stack_args[1])
        elif cmd == OP.LTE:
            stack.push(stack_args[0] <= stack_args[1])
        elif cmd == OP.GTE:
            stack.push(stack_args[0] >= stack_args[1])
        elif cmd == OP.ADD:
            stack.push(stack_args[0] + stack_args[1])
        elif cmd == OP.SUB:
            stack.push(stack_args[0] - stack_args[1])
        elif cmd == OP.MUL:
            stack.push(stack_args[0] * stack_args[1])
        elif cmd == OP.DIV:
            stack.push(stack_args[0] / stack_args[1])
        elif cmd == OP.MOD:
            stack.push(stack_args[0] % stack_args[1])
        elif cmd == OP.EQ_CONST:
            stack.push(stack_args[0] == const_args[0])
        elif cmd == OP.NE_CONST:
            stack.push(stack_args[0] != const_args[0])
        elif cmd == OP.LT_CONST:
            stack.push(stack_args[0] < const_args[0])
        elif cmd == OP.GT_CONST:
            stack.push(stack_args[0] > const_args[0])
        elif cmd == OP.LTE_CONST:
            stack.push(stack_args[0] <= const_args[0])
        elif cmd == OP.GTE_CONST:
            stack.push(stack_args[0] >= const_args[0])
        elif cmd == OP.ADD_CONST:
            stack.push(stack_args[0] + const_args[0])
        elif cmd == OP.SUB_CONST:
            stack.push(stack_args[0] - const_args[0])
        elif cmd == OP.MUL_CONST:
            stack.push(stack_args[0] * const_args[0])
        elif cmd == OP.DIV_CONST:
            stack.push(stack_args[0] / const_args[0])
        elif cmd == OP.MOD_CONST:
            stack.push(stack_args[0] % const_args[0])
        elif cmd == OP.NUNIQUE:
            stack.push(groupby_index(stack_args[0]).nunique())
        print(stack.stack)
    # op, args = cmd['op'], cmd['args']
    # print(op, args)
    # op, args = OP(op), args
    # print(op, args)
    # assert isinstance(op, OP)
    # assert isinstance(args, op.value[1])


if __name__ == '__main__':
    from pathlib import Path
    import yaml
    BASE_DIR = Path(__file__).resolve().parent
    run(yaml.safe_load('''

    - load_col: a
    - nunique
    - eq_const: 1

    '''))