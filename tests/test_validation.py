from context import kye

def get_errors(text, data):
    api = kye.compile(text)
    model_name = [model.ref for model in api.models.values()][-1]
    api.from_records(model_name, data)
    return api.errors

def is_valid(text, data):
    return len(get_errors(text, data)) == 0

def test_value_is_coercible():
    USER = '''
    type UserId: Number

    model User(id) {
        id: UserId,
        name: String,
        is_admin: Boolean,
    }
    '''

    assert is_valid(USER, [{
        'id': 1,
        'name': 'Joe',
        'is_admin': True,
    }])

    assert is_valid(USER, [{
        'id': '1.0',
        'name': 1,
        'is_admin': 1,
    }])

    assert get_errors(USER, [{
        'id': 'user_01',
        'name': 'bill',
        'is_admin': 'sure',
    }]) == {
        ('UserId', 'INVALID_VALUE'),
        ('Boolean', 'INVALID_VALUE'),
    }

def test_undefined_columns():
    USER = '''
    model User(id) {
        id: Number,
        name+: String,
        age?: Number,
        tags*: String,
    }
    '''

    assert is_valid(USER, [{
        'id': 1,
        'name': 'Joe',
    }])

def test_validate_cardinality():
    USER = '''
    model User(id) {
        id: Number,
        name+: String,
        age?: Number,
        tags*: String,
    }
    '''

    assert is_valid(USER, [{
        'id': 1,
        'name': 'Joe',
        'age': None,
        'tags': [],
    }])

    assert get_errors(USER, [{
        'id': 1,
        'name': None,
        'age': 21,
    }, {
        'id': 1,
        'age': 23,
    }]) == {
        ('User.name', 'NOT_NULLABLE'),
        ('User.age', 'NOT_MULTIPLE'),
    }

def test_validate_recursive():
    USER = '''
    model User(id) {
        id: Number,
        friends*: User,
    }
    '''

    assert is_valid(USER, [{
        'id': 1,
        'friends': [{
            'id': 2,
            'friends': [{ 'id': 1 }],
        },{
            'id': 3,
            'friends': [{ 'id': 1 }, { 'id': 2 }],
        }],
    }])

def test_load_different_types():
    api = kye.compile('''
    model User(id) {
        id: Number,
        name: String,
        admin: Boolean,
    }
    ''')

    api.from_records('User', [{
        'id': 1,
        'name': 'Joe',
        'admin': True,
    }, {
        'id': 2,
        'name': 'Bill',
        'admin': False,
    }])

    # Second load uses different types
    # but the 1.0 record should match with the 1 record
    api.from_records('User', [{
        'id': 1.0,
        'name': 'Joe',
    }, {
        'id': 1.2,
        'name': 'Sally',
        'admin': False,
    }])

    assert api.errors == set()

def test_conflicting_loads():
    api = kye.compile('''
    model User(id) {
        id: Number,
        name: String,
    }
    ''')

    api.from_records('User', [{
        'id': 1,
        'name': 'Joe',
    }, {
        'id': 2,
        'name': 'Bill',
    }])

    api.from_records('User', [{
        'id': 1,
        'name': 'Joey', # conflicting name
    }])

    assert api.errors == {
        ('User.name', 'NOT_MULTIPLE')
    }

def test_index_collision():
    USER = '''
    model User(id)(name) {
        id: Number,
        name: String,
    }
    '''

    assert get_errors(USER, [{
        'id': 1,
        'name': 'Joe',
    }, {
        'id': 2,
        'name': 'Joe', # two people are not allowed to have the same name of Joe
    }]) == {
        ('User', 'NON_UNIQUE_INDEX'),
    }

def test_ambiguous_index():
    USER = '''
    model User(id)(employee_id) {
        id: Number,
        employee_id: Number,
    }
    '''

    assert get_errors(USER, [{
        'id': 1,
        'employee_id': 10001,
    }, {
        'id': 2,
        'employee_id': 10002,
    }, {
        'id': 3,
        'employee_id': 2, # Not allowed because it could be confused with the id of a different user
    }]) == {
        ('User', 'NON_UNIQUE_INDEX'),
    }