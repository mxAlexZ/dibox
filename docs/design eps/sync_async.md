# Non-async support

Current non-async implementation can only resolve already instantiated objects since object creation is always async. It limits usability in sync contexts. One of the solutions is to add sync factory versions and throw exceptions when async-only features are used in sync mode.

# provide() / resolve() / get() / []
- `box.provide(Type)`: Auto-wires and constructs the entire dependency graph for `Type` based on type hints. This is the "all-in" approach.
- `box.resolve(Type)`: It is currently confusing name and should be revisited. It is a sync method that only returns already instantiated objects. It does not create new instances. Should it be  renamed to `get()` and/or extended as [] operator?
