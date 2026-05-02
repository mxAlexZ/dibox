# Ideas

## Active roadmap

**Dependency graph introspection** — `validate()` and `graph()` are specced in [EP: Diagnostics](./diagnostics.md). Low implementation cost, high DX value. Named binding modules would make the output more useful.

**Test module composition helpers**

```python
test_bindings = make_test_bindings(
    payment_gateway=FakeGateway,
    invoice_storage=InMemoryInvoiceStorage,
)

async with DIBox() as box:
    box.add_bindings(test_bindings)
```

Tests should compose isolated binding modules. Helper APIs can reduce fixture boilerplate,
but they must preserve graph isolation rather than encourage fallback to non-test
services.

**Startup initialization mode**

Current behavior is lazy: instances are created on first `provide()`. Some apps want eager startup validation — construct all singletons at container entry to fail fast.

```python
async with DIBox(startup_init=True) as box:
    ...  # all registered singletons resolved here
```

Note on terminology: this is distinct from *implicit self-binding* (sometimes called "eager binding"). Startup initialization is about *when* known bindings are resolved, not *whether* unbound types are constructed.

**Async-first, sync-compatible** — worth documenting the sync story clearly: `box.get()` for pre-resolved instances, `@inject` handles both sync and async decorated functions.

---

## Deferred

Ideas that are plausible but waiting for a clearer use-case before design work begins.

**Named binding modules**

```python
bindings = BindingBox(name="billing")
```

Optional module identity would improve error messages, debug logging, `validate()`, and
`graph()` output. Explicit names should be the base feature; automatic names inferred
from the defining Python module can be considered later as convenience syntax.

**Resolver with call-time arguments**

`container_resolver` is currently `Callable[[], ContainerProtocol]` — no arguments. A future version could pass call-time context to the resolver:

```python
# hypothetical — not implemented
session_api = Injector(container_resolver=lambda req: req.state.session_container)

@session_api.inject
async def update_cart(request: Request, cart: Injected[ShoppingCart]): ...
```

This would cover per-request scoping without a contextvar. Open questions: what the resolver protocol looks like (all positional args? only kwargs? a typed protocol?) and whether the added complexity is justified given contextvar-based scoping already covers most cases. Revisit when per-request scoping requirements are clearer.

**Non-destructive signature mode**

The current implementation is always destructive: injected parameters are removed from `__signature__`. A non-destructive mode would keep all parameters visible and inject via defaults or call-time filling instead.

Demand is likely lower for framework entry points (destructive mode is usually preferred there) but potentially meaningful for internal tooling and reflection-heavy code. `SignatureModification` exists in source as a placeholder; not yet wired.


## Archived decisions

**`ArgumentStrategy` / `OPT_OUT` mode** — `OPT_OUT` (inject any typed param) was removed. `OPT_IN` via `Injected[...]` is sufficient: it captures injection intent explicitly without ambiguity about which parameters the container manages. The marker annotation also communicates DI intent at decoration time, before the container is active, which is necessary for import-time framework integration.

**`@injector` bare call** — calling `@injector` directly (without `.inject`) is supported for backward compatibility but `@injector.inject` is the canonical form, consistent with `@container.inject`.
