## Stage 2 TODO:

### Parser
- [ ] Allow AST definition to list everywhere it is used
- [x] Allow AST to be aware of position in document
- [x] Allow for sub model definition outside of edge definition
- [x] Refactor to create a base "type" class
- [x] Move cardinality symbol to postfix the edge name instead of the type
- [x] Add expressions

### Validation
- [x] Figure out where to implement the combining of composite indexes ( and normalizing set indexes )

----
## Stage 3 TODO:

### Parser
- [ ] Allow operation definitions
- [ ] Allow null definition
- [ ] Allow type edge definitions
- [ ] Allow lambda type definitions
- [ ] Pre-process flattening type definitions and renaming local identifiers