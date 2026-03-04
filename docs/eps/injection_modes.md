# @inject decorator customization and usage

## Old (current) behavior and motivation for change:
```python
@inject()
def my_function(arg1: Injected[Type1], arg2: Injected[Type2]):
    ...

@inject_all(container, InjectMode.All)
def my_function(arg1: Type1, arg2: Type2, arg3: NonInjected[Type3]):
    ...

# custom context-aware injection (wasn't implemented)
@inject(lambda request: create_request_scoped_container(request)):
def my_function(requestt , arg2: Injected[Type2]):
    ...
```

Our current `@inject` API requires developers to repeatedly declare the resolution strategy and injection modes at the site of every decorated function. When integrating with frameworks like FastAPI (which requires destructive signature modifications to hide injected args) or building request-scoped applications, this leads to heavy boilerplate `@inject( ...)` on every single route.


# Design Proposal: Dual-Paradigm Dependency Resolution (Declarative vs. Imperative)

## Motivation:
A robust Dependency Injection framework must support two distinct architectural phases: Import-Time (when integrating with external frameworks like FastAPI/Typer that rely on static signature analysis) and Runtime (when executing internal domain logic where the container's state is fully known).

Core Philosophy: Progressive Disclosure of Complexity
The framework must provide a frictionless, zero-configuration experience for the majority of standard use cases (scripts, simple apps), while offering powerful, highly configurable abstractions for the remaining complex use cases. Therefore, basic use cases should require minimal boilerplate and no addtional abstractions - it should be enough to use only dibox methods.

## The Injector decorator API (Declarative / Import-Time)

Motivation: External frameworks (like FastAPI or Typer) use strict static analysis on function signatures at import-time. The injection decorator acts as a bridge between the framework's HTTP/CLI routers and our DI system. Because it is "blind" to the runtime container state at import-time, it relies on explicit Strategy configurations, like `Injected[...]` annotations. It manages __signature__ mutation (to hide injected args from OpenAPI/CLIs) and defines how to resolve the container dynamically at runtime (e.g., extracting from a Request object or a contextvar).


## Convenience Decorators

- `@inject` (global scope)
    Purpose: The zero-boilerplate option. Under the hood, it creates a default Injector linked to a global container instance. From historical point of view, this is the original `@inject` behavior, but it should be changed from being bound to a single global container to retrieving the container from contextvars.

    Example:
    ```python
    @inject
    def run_report(db: Injected[DB]): ...
    ```

- `@container.inject`

    Purpose: Convenience wrapper. For simple applications relying on a global container, this provides a zero-configuration decorator. Under the hood, it creates a default Injector linked to itself.

    Example:
    ```python
    @container.inject
    def run_report(db: Injected[DB]): ...
    ```

## Injector: A reusable, configurable decorator factory that encapsulates both the container resolution strategy and the injection mode.
Instead of configuring the decorator at the function level (e.g. `@inject_all(container, InjectMode.All)`), developers instantiate an Injector once per architectural domain (e.g., one for the API layer, one for background workers). This object stores the container resolution strategy (e.g., extracting from a request or a contextvar) and the injection mode (e.g., destructive vs. adding default values). It then exposes an .inject method that acts as the decorator.

- `@api or @api.inject`

    Purpose: Applies the configured injection rules to the route or entry point. Modifies the __signature__ to hide injected arguments from OpenAPI/CLI parsers, and resolves the container dynamically at runtime (e.g., via contextvars or request.state).

    Example:
    ```python
    global_container = DIBox()
    app_api = Injector(
        container=global_container, # Passes the instance directly!
        signature=SignatureMode.DESTRUCTIVE
    )
    # 2. Session-Level Setup for dependencies that require context (e.g., tied to an active HTTP request/session).
    session_api = Injector(
        resolver=lambda request: request.state.session_container,
        signature=SignatureMode.DESTRUCTIVE
    )

    @app_api
    async def get_system_config(config: Injected[AppConfig]):
        """
        Level 1 Complexity: Zero context required.
        The Injector just pulls from the static `global_container` passed at import time.
        """
        return config.get_settings()

    @session_api
    async def update_user_cart(request: Request, cart: Injected[ShoppingCart]):
        """
        Level 2 Complexity: Highly context-aware.
        The Injector dynamically executes the resolver to find the container for this specific user.
        """
        return cart.add_item()
    ```


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
