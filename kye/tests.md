- Number fields are checked to be numbers
- not defined fields are not checked
- fields only defined in one instance are checked if cardinality is one or more
- If edge is set to a model, check to see if values are within the index of that dataframe
- If edge is set to a const
  - check to see that all values are set to that value
  - save edge as the const and not the series
- If edge is part of the index, bring it out into it's own column
- Make sure edge values retain their dataframe's index so that they can be joined and compared later
- Use the callee's environment within a filter, but add the current 'this' to it
- Edges identifiers should be relative to the current type context (and any filters applied to the context)