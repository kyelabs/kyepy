# Kye Validation Tool
Kye is a validation tool in progress that allows you to define models to validate your data against.

# Getting Started

### Install
```bash
pip install kye
```

### Run
Pass the location of the kye file, the data (`.csv`, `.json` or `.jsonl`) file, and the name of the Model to evaluate the data against. If the data does not pass the model's assertions then the errors and errant data will be displayed.
```
kye user.kye --data users.csv --model User
```

Models are defined in a `.kye` file using the Kye language. 

The Kye language can optionally be compiled into a json or yaml file. Using the `-c` flag followed by a path to a `.json` or `.yaml` file. Run the compiled file like you would a normal `.kye` file
```
kye user.kye -c user.kye.yaml
kye user.kye.yaml --data users.csv --model User
```

### Kye Models
```kye
User(id)(username) {
  id: Number
  username: String
  name: String
  age?: Number

  assert age > 0 & age <= 120
}
```

#### Models

The above Kye script defines a `User` table.
Table names must be upper-cased.

#### Indexes

The name of the table is followed by its index definition.
The `(id)(username)` means that we expect
both the `id` or `username` columns to be able
to uniquely identify a record.

Composite indexes are defined by listing multiple
column names within a single set of parenthesis ex. `(id, username)`

#### Columns

Column names must start with a lowercase and not contain 
spaces or other special characters. If the source data has
column names that don't follow these rules, then you can specify
the full column name in quotes after the column name.
```
  id "User Id": Number
```

The column definitions specify the value type as `Number`, `String` or `Boolean`. More data types like date/time and user defined types are coming soon.

You can specify whether the column allows null values by prefixing the colon with a `?`
```
age?: Number
```

You can also specify if the column allows multiple values (like an array of values) by using `+` if you expect at least one value, or `*` if it is okay to have no values.
```
# Expect at least one version
versions+: String

# It's okay for a post to have no tags
tags*: String 
```

#### Assertions
You can specify extra assertions through the `assert` keyword. Just write an expression that evaluates to true or false, and the rows that evaluate to false will be flagged. You can reference columns by their names.

Expressions support the basic operations:
- `+ - * / %` math
- `== != >= > < <=` comparison
- `! & | ^` logical (not, and, or, xor)
- `()` parenthesis