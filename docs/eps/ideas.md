# Ideas worth exploring

**Dependency graph introspection**

```python
app_box.visualize()  # renders Mermaid/Graphviz of the dependency graph
app_box.validate()   # checks for cycles, missing bindings, scope mismatches
```

Useful for debugging and onboarding. Low implementation cost, high DX value.

**Testing utilities**

```python
async with app_box.override({PaymentGateway: MockGateway}) as test_box:
    ...
```

A thin wrapper over nesting, but makes the intent explicit. Could also support `app_box.override_factory(...)` for partial mocks.

**Lazy vs. eager resolution**

Current behavior is lazy (instances created on first `provide()`). Some apps want eager startup validation — create all singletons at container entry to fail fast.

```python
async with DIBox(eager=True) as box:
    ...  # all APP-scoped bindings resolved here
```

**Async-first, sync-compatible**

DIBox is already async-native. Worth documenting the sync story clearly: `box.get()` for pre-resolved instances, `@inject` handles both sync and async decorated functions. This is a selling point over frameworks that bolt async on later.



### What would make DIBox best-in-class

1. **Zero-config happy path** — `@inject` just works for simple apps. No container setup required for the common case.

2. **Progressive complexity** — nesting → resolver → explicit scopes. Each level unlocks power without invalidating simpler patterns.

3. **Type safety everywhere** — bindings, scopes, and context forwarding all checkable by pyright. No stringly-typed APIs.

4. **First-class async** — not an afterthought. Lifecycle management via `async with` is natural and correct.

5. **Debugging affordances** — graph visualization, validation, clear error messages for scope mismatches and missing bindings.

6. **Minimal API surface** — resist feature creep. Every new concept must justify its weight.
