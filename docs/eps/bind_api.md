
# bind(...) signature

## Accepted approach:
 Separate arguments for different binding types:
```python
box.bind(type, target)
box.bind(type, name, target)
box.bind(type, name, factory=...)
box.bind(type, name, instance=...)
box.bind(type, name, target=...)
```

## Examples of current usage patterns

- `box.bind(type, instance)`  # Bind type to instance
- `box.bind(type, Implementation)`  # Bind interface/abstract to implementation (positional)
- `box.bind(type, to=implementation, ...)`  # Bind type to implementation with kwargs
- `box.bind(type, to=factory_func)`  # Bind type to factory (sync or async)
- `box.bind(type, to=factory_func, a=..., b=...)`  # Bind type to factory with extra kwargs
- `box.bind(type, to=instance, name="..." )`  # Named binding
- `box.bind(type, to=factory_func, name="..." )`  # Named factory binding
- `box.bind(None, name="...", to=instance)`  # Untyped named binding
- `box.bind(lambda t: predicate(t), to=instance_or_factory)`  # Predicate-based binding
- `box.bind(type, to=lambda t: t(...))`  # Factory with type argument

## Rejected ideas
- Fluent API style:
  `box.for_type(type).to(factory).named('orders').with_kwargs(a=..., b=...)`

- Explicit factory binding method:
    `box.bind_factory(type, factory_func, name="_name_")`
    `box.bind_instance(type, instance, name="_name_")`
    `box.bind_implementation(type, implementation, name="_name_")`
