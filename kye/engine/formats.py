import pandas as pd
import numpy as np
from typing import Optional
import re

def parse_number_format(format_str: str):
    def cast_int(n: str):
        return int(n) if n != '' else None
    m = re.search(r'^([+-]?)(\d*)(,?)(?:\.(~?)(\d+))?([bdoxXnf%]?)$', format_str)
    sign = m.group(1) or None
    lpad = m.group(2).startswith('0') and len(m.group(2)) > 1
    width = cast_int(m.group(2))
    separator = m.group(3) or None
    rpad = m.group(4) != '~'
    precision = cast_int(m.group(4) or '')
    unit = m.group(5) or None
    return {
        'sign': sign,
        'lpad': lpad,
        'rpad': rpad,
        'width': width,
        'separator': separator,
        'precision': precision,
        'unit': unit
    }

def as_number(col: pd.Series, format: str):
    format = parse_number_format(format)
    split = col.astype(str).str.extract(r'^([+-]?)([0-9,]*)(?:\.([0-9]*))?$')\
        .set_axis(['sign','base','decimal'], axis=1).fillna('')
    invalid = split.isna().all(axis=1)
    if format['separator'] == ',':
        invalid |= split.base.str.contains(',') & ~split.base.str.fullmatch('^[0-9]{1,3}(,[0-9]{3})*$')
        col = col.str.replace(',','')
    else:
        invalid |= split.base.str.contains(r'\D', regex=True)
    if format['width'] is not None:
        if format['width'] == 0:
            invalid |= split.base.str.lstrip('0').str.len() > format['precision']
        invalid |= split.base.str.len() > format['width']
    if format['precision'] is not None:
        if format['precision'] == 0:
            invalid |= split.decimal.str.rstrip('0').str.len() > format['precision']
        else:
            invalid |= split.decimal.str.len() > format['precision']
    return col.where(~invalid, np.nan).astype(float)