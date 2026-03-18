## Inject Decorator API

### Motivation

The original decorator style required per-function configuration:

```python
@inject(container, mode)
def route_a(...): ...

@inject(container, mode)
def route_b(...): ...
```

This causes repetitive boilerplate and makes architectural changes expensive (switching container strategy means editing many entry points).

For import-time integration with frameworks (FastAPI, Typer), decorators also need to cooperate with strict signature inspection. That is why marker annotations (`Injected[...]`) exist: they communicate DI intent explicitly at decoration time, before the container is active.

The direction here is progressive disclosure:
- simple apps should work with minimal ceremony,
- larger apps should be able to centralise policy once per architectural domain.

### Convenience decorators

The encouraged default forms are:
- `@inject`
- `@container.inject`

`@inject` is backed by `DIBox.from_context` — a contextvar that holds the container entered via `async with box:`. Injection happens at call time from whatever container is active in the current async task or thread. This makes `@inject` safe for parallel execution (no process-wide global) and means it works naturally with framework lifespans: decorate at import time, activate the container at startup.

`@container.inject` keeps the same low ceremony while making container ownership explicit and fixed at decoration time.

### Injector as domain-level configuration

`Injector` is for cases where you want one reusable policy per architectural domain (for example app-level routes vs. session-level routes), then apply it consistently at entry points.

```python
app_box = DIBox()

app_api = Injector(app_box)

# Late-bound: resolves from context at call time, same as @inject
session_api = Injector(container_resolver=DIBox.from_context)

@app_api.inject
async def get_system_config(config: Injected[AppConfig]):
    return config.get_settings()

@session_api.inject
async def update_user_cart(request: Request, cart: Injected[ShoppingCart]):
    return cart.add_item()
```

`@injector` (without `.inject`) is supported and should remain supported because it costs little, but `@injector.inject` is the canonical documented form, consistent with `@container.inject`.

`ArgumentStrategy` / `OPT_OUT` mode was removed from the implementation. The `OPT_IN` default (inject only `Injected[...]`-annotated params) is sufficient for all current use cases and keeps intent explicit.

### `container_resolver` — context-aware and scoped injection

`Injector` accepts either a fixed `container` or a `container_resolver: Callable[[], ContainerProtocol]` (keyword-only). Exactly one must be provided.

- `container=` for static, import-time known container.
- `container_resolver=` for runtime-selected container — per-request, per-session, or context-based.

`DIBox.from_context` is the built-in resolver that reads the contextvar, and it is also what plain `@inject` uses internally. Custom resolvers can read from request state, thread-locals, or any other runtime source.

This is the bridge between scoped container lifecycle and decorator-based entry points — resolver-based `Injector` instances remain the right tool once per-request scoping lands.

```python
# These two are equivalent:
@inject
async def handler(svc: Injected[MyService]): ...

_injector = Injector(container_resolver=DIBox.from_context)
@_injector.inject
async def handler(svc: Injected[MyService]): ...
```

### Open: resolver with call-time arguments

Currently `container_resolver` is `Callable[[], ContainerProtocol]` — it takes no arguments. In theory it could receive arguments from the wrapped function's call (e.g. the `request` object in a web handler), allowing patterns like:

```python
# hypothetical — not implemented
session_injector = Injector(container_resolver=lambda req: req.state.session_container)

@session_injector.inject
async def update_cart(request: Request, cart: Injected[ShoppingCart]):
    ...
```

This would make resolvers more powerful for per-request scoping without relying on a contextvar at all. The open questions are what the resolver signature should look like (all positional args? only kwargs? a typed protocol?) and whether the added complexity is justified given that contextvar-based scoping covers most cases already. Leaving open; revisit when per-request scoping requirements are clearer.

### Open: non-destructive signature mode

Current implementation is always destructive: injected params are removed from `__signature__`.

Potential non-destructive mode would keep all parameters visible and inject via defaults/call-time filling.

Demand perspective:
- likely lower demand for FastAPI/Typer entry points (destructive mode is usually preferred there),
- potentially meaningful for internal tooling, debugging, reflection-heavy code, and teams that treat explicit callable signatures as part of developer ergonomics.

So this looks less like a universal must-have and more like a targeted opt-in capability. Still worth planning, but lower priority than scoped containers.

Note: `SignatureModification` exists in source as a placeholder and is not wired yet.


## Imperative / Runtime-Aware API (container.call and container.partial) and greedy resolution

The Container operates at runtime. Because it physically exists in memory and knows its exact provider registry, it can use Greedy Resolution. It looks at a function signature, binds any argument it has a provider for, and ignores the rest. No Injected[...] type hints are required.

 - `container.call(func, *args, **kwargs)`

    Purpose: Immediate, one-off execution of a function with auto-wired dependencies. Perfect for CLI scripts, cron jobs, or task queues.

    Example:
    ```python
        # Look ma, no Injected[...] annotations!
        def process_checkout(user_id: int, db: Database, stripe: StripeClient):
            pass
        # 'db' is auto-wired from the container, 'user_id' is passed explicitly
        container.call(process_checkout, user_id=42)
    ```

 - `container.partial(func, *args, **kwargs)`

    Purpose: Delayed execution. Acts as a DI-aware functools.partial. Binds resolved dependencies and returns a callable to be executed later.

    Example:
    ```python
        # Locks in the 'db' dependency now, to be executed later
        checkout_func = container.partial(process_checkout)
        checkout_func(user_id=42)
    ```
