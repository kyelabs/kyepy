import pandas as pd
import numpy as np
from typing import Optional
import re

def as_boolean(col: pd.Series, format: str):
    if pd.api.types.infer_dtype(col) == 'boolean':
        return col
    return col.where(col.apply(pd.api.types.is_bool), np.nan)

def as_string(col: pd.Series, format: str):
    if pd.api.types.is_string_dtype(col):
        return col
    return col.astype(str, errors='ignore')

def parse_number_format(format_str: str):
    def cast_int(n: str):
        return int(n) if n is not None and n != '' else None
    m = re.search(r'^(-?\d+)?(,?)(?:\.(-?\d+))?$', format_str)
    assert m is not None, 'Invalid format string'
    start = cast_int(m.group(1))
    thousands = m.group(2) or None
    end = cast_int(m.group(3))

    if start is not None and end is not None:
        assert (start + end) > 0, 'Must have at least 1 significant figure'
    return {
        'start': start,
        'thousands': thousands,
        'end': end,
    }

def as_number(col: pd.Series, format: str):
    # TODO: compute a correctly sized dtype based on the format
    # and cast the column using that dtype, only marking it as invalid
    # if the value wouldn't fit in that dtype
    format = parse_number_format(format)
    if pd.api.types.is_numeric_dtype(col):
        valid = col.notnull()
        if format['start'] is not None:
            # TODO: Use the correct base for binary, octal, and hex values
            valid &= col < (10 ** format['start'])
        if format['end'] is not None:
            if format['end'] > 0 and pd.api.types.is_integer_dtype(col):
                valid = False
            elif format['end'] == 0:
                valid &= col % 1 == 0
        valid |= col == 0
        return col.where(valid, np.nan)
    else:
        col = col.astype(str)
        split = col.str.extract(r'^([+-]?)([0-9,]*)(?:\.([0-9]*))?$')\
            .set_axis(['sign','whole','decimal'], axis=1)
        invalid = split.isna().all(axis=1)
        split = split.fillna('')
        if format['thousands'] == ',':
            invalid |= ~(split.whole.str.fullmatch('^[0-9]{1,3}(,[0-9]{3})*$') | ~split.whole.str.contains(','))
            col = col.str.replace(',','')
        else:
            invalid |= split.whole.str.contains(r'\D', regex=True)
        if format['start'] is not None:
            invalid |= split.whole.str.lstrip('0').str.len() > max(format['start'], 0)
            if format['start'] < 0:
                invalid |= split.decimal.str.slice(stop=-format['start']).str.contains(r'[1-9]')
        if format['end'] == 0:
            invalid |= split.decimal.str.rstrip('0').str.len() > 0
        return pd.to_numeric(col.where(~invalid, np.nan))