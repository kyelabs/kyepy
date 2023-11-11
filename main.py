from pathlib import Path
import kye
DIR = Path(__file__).parent

if __name__ == '__main__':
    with open(DIR / 'examples/yellow.kye') as f:
        text = f.read()
    
    models = kye.compile(text)
    
    models.Yellow.from_records([{
        'id': 1,
        # 'size': 1,
        'meep': {
            "id": 1,
        },
        'mother': { 
            'id': 1,
            'admin': False,
            'name': 'Joe',
            'friends': [{
                'id': 3,
                'name': 'Bob',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        },
        'father': {
            'id': 2,
            'admin': False,
            'name': 'Mary',
            'friends': [{
                'id': 5,
                'name': 'Susan',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        },
        'tags': [1, 'hi', 'bye']
    },
    {
        'id': 2,
        # 'size': 2,
        'mother': { 
            'id': 3,
            'admin': True,
            'name': 'Bob',
            'friends': [{
                'id': 3,
                'name': 'Bob',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        },
        'father': {
            'id': 4,
            'admin': False,
            'name': 'Sally',
            'friends': [{
                'id': 5,
                'name': 'Susan',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        },
    }
    ])

    models.Yellow.from_records([{
        'id': 1.0,
        'size': None,
        'tags': ['hi', 'meep']
    }, {
        'id': 2,
        'size': 3,
        'meep': { 'id': 3 },
    }])

    for model_name, table in models.tables.items():
        print(model_name)
        print(table)

    print('Errors:')
    print(models.errors)
    print('hi')