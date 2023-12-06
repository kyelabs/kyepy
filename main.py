from pathlib import Path
import kye
DIR = Path(__file__).parent

if __name__ == '__main__':
    with open(DIR / 'examples/yellow.kye') as f:
        text = f.read()
    
    api = kye.compile(text)
    api.from_records('User',[{
        'kind': 1,
        'name': 'ben',
        'id': 4,
        'hi': 2
    }])

    # print(kye.compile('''
    # type UserId: Number

    # model User(id) {
    #     id: UserId,
    #     name: String,
    #     is_admin: Boolean,
    # }
    # ''').from_records('User', [{
    #     'id': 1,
    #     'name': 'Joe',
    #     'is_admin': True,
    # }]).errors)