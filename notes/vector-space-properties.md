1. Closure under addition
```
sum(Vector, Vector) -> Vector
```

2. Closure under scalar multiplication
```
scale(Vector, Scalar) -> Vector
```

3. Associativity of addition
```
sum(sum(u, v), w) == sum(u, sum(v, w))
```

4. Commutativity of addition
```
sum(u, v) == sum(v, u)
```

5. Identity element of addition
```
sum(u, NULL) == u
```

6. Inverse element of addition
```
sum(u, -u) == NULL
```

7. Associativity of multiplication
```
scale(scale(c, d), u) == scale(u, scale(d, u))
```

8. Identity of multiplication
```
scale(u, 1) == u
```