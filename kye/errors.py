ERROR_CLASSES = {}

class Error:
    def __init__(
            self,
            table_name,
            column_name,
            num_rows,
            num_indexes,
            num_values,
            row_example,
            idx_example,
            val_example,
        ):
        self.table_name = table_name
        self.column_name = column_name
        self.num_rows = num_rows
        self.num_indexes = num_indexes
        self.num_values = num_values
        self.row_example = row_example
        self.idx_example = idx_example
        self.val_example = val_example
    
    def __init_subclass__(cls) -> None:
        assert hasattr(cls, 'name')
        ERROR_CLASSES[cls.name] = cls

    @property
    def message(self) -> str:
        raise NotImplementedError('Not implemented for Abstract Class')

class ConflictingIndexError(Error):
    name = 'CONFLICTING_INDEX'

    @property
    def message(self):
        if self.column_name is not None:
            if self.num_rows > 1:
                return f'''Found conflicting "{self.column_name}" values across {self.num_indexes} rows'''
            else:
                return f'''Found conflicting "{self.column_name}" values for row {self.row_example}'''
        else:
            return f'''Found conflicting index values across {self.num_rows} rows'''


class IncompleteIndexError(Error):
    name = 'INCOMPLETE_INDEX'

    @property
    def message(self):
        return f'''Unable to complete multi-index for {self.num_rows} rows'''

class MissingIndexError(Error):
    name = 'MISSING_INDEX'

    @property
    def message(self):
        if self.num_rows > 1:
            return f'''Missing required "{self.column_name}" index in {self.num_rows} rows'''
        else:
            return f'''Missing the required "{self.column_name}" index for row {self.row_example}'''

class MissingEdgeError(Error):
    name = 'MISSING_EDGE'

    @property
    def message(self):
        if self.num_indexes > 1:
            return f'''Missing required "{self.column_name}" value in {self.num_indexes} rows'''
        else:
            return f'''Missing the required "{self.column_name}" value for row {self.row_example}'''

class ConflictingEdgeError(Error):
    name = 'CONFLICTING_EDGE'

    @property
    def message(self):
        if self.num_indexes > 1:
            return f'''Found conflicting "{self.column_name}" values across {self.num_indexes} rows'''
        else:
            return f'''Found conflicting "{self.column_name}" values for row {self.row_example}'''

class InvalidValueTypeError(Error):
    name = 'INVALID_VALUE_TYPE'
    @property
    def message(self):
        if self.num_indexes > 1:
            return f'''Found invalid "{self.column_name}" value types (ex. {repr(self.val_example)}) across {self.num_indexes} rows'''
        else:
            return f'''Found invalid "{self.column_name}" value type ({repr(self.val_example)}) for row {self.row_example}'''

def error_factory(err_type, **kwargs):
    assert err_type in ERROR_CLASSES
    return ERROR_CLASSES[err_type](**kwargs)