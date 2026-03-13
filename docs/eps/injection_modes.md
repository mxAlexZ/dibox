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

For import-time integration with frameworks (FastAPI, Typer), decorators also need to cooperate with strict signature inspection. That is why marker annotations (`Injected[...]` / `NotInjected[...]`) exist: they communicate DI intent explicitly in a context where the runtime container state is not fully available yet.

The direction here is progressive disclosure:
- simple apps should work with minimal ceremony,
- larger apps should be able to centralise policy once per architectural domain.

### Convenience decorators

The encouraged default forms are:
- `@inject`
- `@container.inject`

`@inject` is currently backed by `global_dibox`, and the accepted backlog item is to move it to contextvar-based container resolution. Once that lands, plain `@inject` should cover more real-world cases without manual wiring.

`@container.inject` keeps the same low ceremony while making container ownership explicit.

### Injector as domain-level configuration

`Injector` is for cases where you want one reusable policy per architectural domain (for example app-level routes vs. session-level routes), then apply it consistently at entry points.

```python
global_container = DIBox()

app_api = Injector(
    container=global_container
)

session_api = Injector(
    resolver=lambda request: request.state.session_container
)

@app_api.inject
async def get_system_config(config: Injected[AppConfig]):
    return config.get_settings()

@session_api.inject
async def update_user_cart(request: Request, cart: Injected[ShoppingCart]):
    return cart.add_item()
```

`@injector` (without `.inject`) is supported and should remain supported because it costs little, but `@injector.inject` is the canonical documented form, consistent with `@container.inject`.

`ArgumentStrategy` exists in the current implementation (`OPT_IN` default, `OPT_OUT` available), but it is not the core value proposition of `Injector`. In practice, `resolver` and signature behavior are the bigger differentiators for framework and scoped usage.

### Planned: context-aware injection via resolver

`resolver` is one of the main missing features and the key enabler for scoped/container-per-context patterns.

Without resolver, `Injector` only works with a container known at import time. With resolver, container selection moves to call time, which allows patterns like per-session or per-request containers while keeping route handlers clean.

Design intent:
- `container=` for static, import-time known container.
- `resolver=` for context-aware, runtime-selected container.
- exactly one of them should be provided.

This connects directly to scope support: resolver is the bridge between scoped container lifecycle and decorator-based entry points.

### Planned: non-destructive signature mode

Current implementation is always destructive: injected params are removed from `__signature__`.

Potential non-destructive mode would keep all parameters visible and inject via defaults/call-time filling.

Demand perspective:
- likely lower demand for FastAPI/Typer entry points (destructive mode is usually preferred there),
- potentially meaningful for internal tooling, debugging, reflection-heavy code, and teams that treat explicit callable signatures as part of developer ergonomics.

So this looks less like a universal must-have and more like a targeted opt-in capability. It is still worth planning, but probably after resolver.

Note: `SignatureModification` already exists in source as a placeholder and is not wired yet.


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
