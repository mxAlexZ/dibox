# Opt-in vs All-in design

- **`box.provide(T)`:** Follows an **"All-in"** (auto-wiring) model. It recursively constructs the entire dependency graph for `T` automatically, assuming any type hint is a dependency to be resolved.

- **`@inject` decorator:** Follows an **"Opt-in"** model. It only injects function arguments explicitly wrapped in `Injected[T]`. An `@inject_all` decorator could provide an "All-in" alternative for entry points.

## 1. "All-in" / Auto-Wiring First (Current Core Behavior)
...existing code...

## 2. "Opt-in" / Explicit Injection
...existing code...

## 3. Creative Alternative: Smart injection
...existing code...
