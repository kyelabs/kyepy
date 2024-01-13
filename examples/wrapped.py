import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kye

@kye.validate('Post')
def get_posts():
    return [{
        'id': 0,
        'author': 1,
    }, {
        'id': 1,
        'author': 40,
    }]

@kye.validate('User')
def get_users():
    return [{
        # 'id': 0,
        'name': 'Ben',
        'posts': []
    }, {
        'id': 1,
        'name': 'Bill',
        'posts': [1],
    }, {
        'id': 3,
        'name': 'Bob',
    }]

if __name__ == '__main__':
    print(get_users())
    print(get_posts())