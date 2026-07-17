# Entrypoints

**Status**: Partially Implemented (declarative); Proposed (imperative)

This document describes the different ways to trigger dependency injection in DIBox.

-   See also: [Strict Mode](./strict_mode.md) (for explicit-binding behavior), [Implicit Self-Binding](./implicit_self_binding.md) (for permissive fallback and guardrails).

---

## 1. Declarative Entrypoints: Framework Integration

Declarative entrypoints are essential for integrating with modern Python frameworks like FastAPI, Typer, or cloud SDKs (e.g., Azure Functions).

The Core Problem: These frameworks inspect function signatures at *import time* to build their routing tables, CLI commands, or event handlers. However, the DI container is typically configured and activated much later, at application startup.

The DIBox Solution:
1.  The `Injected[T]` annotation marks a parameter for injection.
2.  The `@inject` decorator wraps the function and rewrites its `__signature__`, removing `Injected[T]` parameters. Frameworks that call `inspect.signature()` at import time see only the remaining parameters and are satisfied.
3.  At *call time*, the wrapper intercepts the call, resolves the `Injected[T]` dependencies from the active container, and forwards them to the original function.

### 1.1. `@inject`

The primary decorator for declarative injection. It uses a context variable (`DIBox.from_context`) to find the currently active container at call time. Because the contextvar is isolated per async task and per OS thread, parallel calls each see their own active container — there is no process-wide global. This makes `@inject` safe for concurrent execution and a natural fit for framework lifespans.

```python
# routes.py — decorated at import time, container not yet active
@inject
async def get_current_user(request: Request, auth: Injected[AuthService]) -> User:
    return await auth.verify_token(request.headers["Authorization"])

# app.py — container activated at startup
async with DIBox() as box:
    box.bind(AuthService)
    # A web framework can now serve requests to get_current_user,
    # and the `auth` service will be correctly injected on every call.
```

-   When to use: The default choice for integrating with any callback-based framework.

### 1.2. `@container.inject`

A method on a container instance that permanently binds the decorated function to that specific container. It ignores the context variable.

```python
box = DIBox()
box.bind(AppConfig)

@box.inject
async def get_system_config(config: Injected[AppConfig]) -> dict:
    return config.get_settings()
```

-   When to use: When the container is a known, long-lived singleton and you want to be explicit about the ownership, bypassing the context variable mechanism.

### 1.3. Advanced: The `Injector` Object

For large applications, it can be useful to centralize injection policy for a specific architectural domain (e.g., `admin_api`, `public_api`). The `Injector` object serves this purpose.

```python
# Reusable policy for all admin routes
admin_api = Injector(container_resolver=DIBox.from_context)

@admin_api.inject
async def create_user(...): ...
```

However, for most use cases, `@inject` is simpler and sufficient. `Injector` was originally conceived to solve problems that the modern context-aware `@inject` now handles automatically. It remains a useful tool for enforcing strict architectural layers but can be considered an advanced feature rather than a primary recommendation.

---

## 2. Imperative Entrypoints: Direct Execution

Imperative entrypoints are for scenarios where you have a container instance in hand and want to directly execute a function with dependencies. They are the ideal tool for scripting, orchestration, and single-shot execution contexts.

Unlike decorators, they do not require `Injected[T]` markers. They inspect the function's signature and fill any parameter the container can provide.

### 2.1. `container.call()`

Immediately execute a function, injecting dependencies and passing through any other arguments. This is especially powerful when a container is created for a specific, short-lived task.

```python
# In a Ray worker or a simple script:
def process_data(source_url: str, db: Database, notifier: Notifier):
    ...

async def run_task(source: str):
    # Container is created, configured with modules, and used for a single call
    async with DIBox() as box:
        box.add_bindings(task_bindings)  # Assumes a BindingBox is defined elsewhere
        # db and notifier are injected; source_url is passed directly
        await box.call(process_data, source_url=source)
```

-   Use Case: CLI commands, background jobs (Celery, Ray), and any situation where you want to trigger a small set of actions on a freshly configured container.

### 2.2. `container.partial()`

Return a callable with dependencies pre-resolved. It acts like `functools.partial` but is DI-aware.

```python
# Dependencies are resolved and bound now...
bound_processor = box.partial(process_data)

# ...and the function is called later with the remaining arguments
bound_processor(source_url="s3://...")
```

-   Use Case: Preparing DI-injected callbacks for systems that are not DI-aware (e.g., schedulers, event buses).

### 2.3. A Note on Resolution Strategy

The power of imperative entrypoints is also their biggest risk, and their behavior is highly dependent on the container's resolution mode.

-   In permissive mode (the default), `call()` is extremely convenient for quick scripts. It will attempt to construct any dependency, which minimizes boilerplate. However, a missing binding can lead to silent misconfigurations.

-   In strict and semi-strict mode, `call()` becomes a safe and predictable tool. It will only inject explicitly bound dependencies, failing immediately if something is missing. This is the recommended approach when using well-defined binding modules, as it guarantees that your function is receiving exactly the dependencies you have configured.

The choice allows you to trade convenience for safety. For a quick, one-off script, the permissive default may be fine. For robust, production-grade orchestration, strict mode is strongly recommended.

## 3. Interaction with Resolution Modes

The selected resolution mode applies uniformly to all entrypoints, ensuring consistent behavior. See [Strict Mode](./strict_mode.md) for strict semantics, [Implicit Self-Binding](./implicit_self_binding.md) for permissive fallback, and [Implicit Creation Policy](./implicit_creation_policy.md) for type eligibility within implicit-binding mode boundaries.

-   Strict mode: Only explicitly bound types are resolved. All entrypoints will raise an error for unbound types.
-   Semi-strict mode: Resolution roots must be explicitly bound, while unbound transitive concrete dependencies may still be implicitly self-bound.
-   Permissive mode (default): Implicit self-binding is used for unbound concrete types permitted by the implicit creation policy. This is convenient but carries risk, especially for imperative entrypoints.
