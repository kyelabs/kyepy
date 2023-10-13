https://datatracker.ietf.org/doc/html/draft-bhutton-json-schema-validation-01#section-6.2.3-2

# Any
type: "null", "boolean", "object", "array", "number", "string"
enum: list of values
const: single value

# Numeric
multipleOf: divisible by
maximum:
exclusiveMaximum:
minimum:
exclusiveMinimum:

# String
maxLength: non-negative integer
minLength: non-negative integer
pattern: regular expression

# MetaData
title:
description:
default:
deprecated:
readOnly:
writeOnly:
examples:


String[length[0..5]]
String[length: ..5]
String.length[0..5]
String[length < 5]

Classroom(id: String)
Classroom(name: String)

Class(class:String) {
  room: Classroom

  room: Classroom.id

  Classroom(id: room_id, name: room_name)
}

Classroom(id: String, name: String)


Person {
  first_name: String
  last_name: String
  birthday: Date[format:"YYYY-MM-DD"]
  address: Address {
    street_address: String
    city: String
    state: String
    country: String
  }
}

Address {
  street_address: String
  city: String
  state: String
  type: "residential" | "business"

  if (type == "business") {
    department: String
  }
}

Address:
  street_address: String
  city: String
  state: String
  type: "residential" | "business"
  if type == "business":
    department: String

PhoneNumber: /^(\([0-9]{3}\))?[0-9]{3}-[0-9]{4}$/

Edge:
  name or pattern:
  type or enum or const:
  expression
  cardinality
  arguments?
  meta:
    title?
    description?
    default?
    deprecated?
    examples?

Model:
  minProperties:
  maxProperties:
  propertyNames: pattern


Composition:
  allOf:
  anyOf:
  oneOf:
  not: