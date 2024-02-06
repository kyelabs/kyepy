import pandas as pd
import numpy as np
from typing import Optional, Literal
from pandas._typing import Dtype
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


class Format:
    pandas_dtype: Dtype

    """ Abstract class for formats """
    def __init__(self, format_str: str):
        pass

    def validate(self, col: pd.Series) -> pd.Series: # errors
        raise NotImplementedError()

    def coerce(self, col: pd.Series) -> pd.Series: # coerced value
        raise NotImplementedError()



class NumberFormatString:
    start: Optional[int]
    end: Optional[int]
    unsigned: bool
    is_integer: bool
    thousands: Optional[str]
    sigfig: Optional[int]
    format: Optional[Literal['u','i','f']]

    def __init__(self, format_str):
        def cast_int(n: str):
            return int(n) if n is not None and n != '' else None
        m = re.search(r'^(-?\d+)?(,?)(?:\.(-?\d+))?([uif]?)$', format_str)
        assert m is not None, 'Invalid format string'
        self.start = cast_int(m.group(1))
        self.thousands = m.group(2) or None
        self.end = cast_int(m.group(3))
        self.format = m.group(4) or None

        if self.format in ('u','i'):
            if self.end is not None:
                assert self.end <= 0, 'Can\'t specify decimal value for integers'
            else:
                self.end = 0
            if self.start is not None:
                assert self.start > 0, 'Can\'t specify negative magnitude for integers'
        
        self.is_integer = self.end is not None and self.end <= 0
        self.unsigned = self.format == 'u'

        self.sigfig = None
        if self.start is not None and self.end is not None:
            self.sigfig = self.start + self.end
            assert self.sigfig > 0, 'Must have at least 1 significant figure'
    
    def to_pandas_dtype(self):
        if self.is_integer:
            if self.format == 'u':
                return np.uint
            else:
                return np.int
        else:
            return np.float

class NumberFormat:
    format: NumberFormatString

    def __init__(self, format_str: str):
        self.format = NumberFormatString(format_str)
        self.dtype = self.format.to_pandas_dtype()

    def validate(self, col: pd.Series) -> pd.Series: # errors
        errors = pd.Series(index=col.index, dtype=str)
        col = col.astype(str)
        split = col.str.extract(r'^([+-]?)([0-9,]*)(?:\.([0-9]*))?$')\
            .set_axis(['sign','whole','decimal'], axis=1)
        errors.loc[split.isna().all(axis=1)] = 'ERROR_NOT_A_NUMBER'
        split = split.fillna('')
        if self.format.unsigned:
            errors.loc[split.sign == '-'] = 'ERROR_NOT_UNSIGNED'
        if self.format.thousands == ',':
            errors.loc[~(split.whole.str.fullmatch('^[0-9]{1,3}(,[0-9]{3})*$') | ~split.whole.str.contains(','))] = 'WARNING_BAD_THOUSANDS'
            split['whole'] = split.whole.str.replace(',','')
        if self.format.end is not None:
            errors.loc[self._greater_than_end(split.whole, split.decimal)] = 'WARNING_MAX_RESOLUTION'
        if self.format.start is not None:
            errors.loc[self._greater_than_start(split.whole, split.decimal)] = 'ERROR_MAX_MAGNITUDE'
        return errors

    def _greater_than_end(self, whole: pd.Series, decimal: pd.Series):
        errors = decimal.str.rstrip('0').str.len() > max(self.format.end, 0)
        if self.format.end < 0:
            errors |= whole.str.slice(start=self.format.end).str.contains(r'[1-9]')
        return errors

    def _greater_than_start(self, whole: pd.Series, decimal: pd.Series):
        errors = whole.str.lstrip('0').str.len() > max(self.format.start, 0)
        if self.format.start < 0:
            errors |= decimal.str.slice(stop=-self.format.start).str.contains(r'[1-9]')
        return errors

    def coerce(self, col: pd.Series) -> pd.Series: # coerced value
        if self.format.thousands and pd.api.types.is_string_dtype(col):
            col = col.str.replace(',','')
        col = col.astype(self.dtype)
        if self.format.end:
            if self.format.end >= 0:
                col = col.round(self.format.end)
            else:
                resolution = 10 ** -self.format.end
                col = (col / resolution).astype(self.dtype) * resolution
        return col

if __name__ == '__main__':
    fmt = NumberFormat('-2u')
    data = pd.Series([1000,100,10,1,0.1,0.01,0.001])
    errors = fmt.validate(data)
    coerced = fmt.coerce(data[errors.isnull() | errors.str.startswith('WARNING_')])
    print('hi')