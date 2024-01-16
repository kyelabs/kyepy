# Kye Validation Tool
Kye is a validation tool in progress that allows you to define and validate
models for your data.

# Getting Started

### Install
```bash
pip install kye
```

### Define Models
Create a file called `models.yaml` in the same directory as your python scripts

Here is an example of a `models.yaml` file:
```yaml
# Define a model for each table
# using the table name as the key
models:
  User:
    # List of indexes means that
    # both `id` and `name` should both be able
    # to uniquely identify a `User`
    indexes:
      - id
      - username
    # Edges are the name and value type of each column
    edges:
      id: Number
      username: String
      name: String
      # Add a `?` to the end of the column name
      # if the value is allowed to be null
      age?: Number
  Post:
    # The `index` field is a shorthand for `indexes`
    # when there is only a single field used to identify a model
    index: id
    edges:
      id: Number
      # Coming soon is the ability to define relationships with other models
      author: User
```

### Usage in Python
Add the `kye.validate('<Model Name>')` decorator to your python loading
functions and library will throw an error if the return value of your
function does not match your defined model.

Right now the validation decorator only works with data that is returned
as a list of dictionaries, but support for more data formats like pandas data frames will soon follow.

```python
import requests

import kye

@kye.validate('User')
def get_users():
  return requests.get('/api/v1/users').json()
```