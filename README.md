
# DIBox

[![release](https://gitlab.com/AlexZee/dibox/-/badges/release.svg)](https://gitlab.com/AlexZee/dibox/-/releases) ![Python Versions](https://img.shields.io/pypi/pyversions/dibox) [![coverage](https://gitlab.com/AlexZee/dibox/badges/main/coverage.svg)](https://gitlab.com/AlexZee/dibox/-/commits/main) [![PyPI - License](https://img.shields.io/pypi/l/dibox)](https://gitlab.com/AlexZee/dibox/-/blob/main/LICENSE)

---

**⚠️ Project Status: Early Development**

This library is in its early stages. The design and API are not yet fully established and may change significantly in future releases. Feedback, suggestions, and contributions are very welcome!

---

Async-native dependency injection framework based on type hints.

- [Installation](#installation)
- [What is DIBox?](#what-is-dibox)
- [Key Features](#key-features)
- [QuickStart](#quickstart)
  - [1. Define your application as usual](#1-define-your-application-as-usual)
  - [2. Wire and Run](#2-wire-and-run)
- [Usage Guide](#usage-guide)
  - [Using Decorators for Injection](#using-decorators-for-injection)
  - [Resource Lifecycle](#resource-lifecycle)
    - [Binding Patterns](#binding-patterns)
    - [Binding Interfaces & Instances](#binding-interfaces--instances)
    - [Factory Functions](#factory-functions)
    - [Named dependencies](#named-dependencies)
    - [Dynamic Predicate-Based Binding](#dynamic-predicate-based-binding)
    - [Resolution Modes](#resolution-modes)
  - [Binding Modules](#binding-modules)
    - [Organizing bindings by feature](#organizing-bindings-by-feature)
    - [Reusing modules across contexts](#reusing-modules-across-contexts)
    - [Overriding bindings for tests](#overriding-bindings-for-tests)
    - [Resolution order](#resolution-order)
- [Why use DIBox?](#why-use-dibox)
  - [The Power of Auto-Wiring](#the-power-of-auto-wiring)
  - [Comparison with Other Frameworks](#comparison-with-other-frameworks)
- [Contributing](#contributing)

## Installation
```
pip install dibox
```

Requires Python 3.11+.

## What is DIBox?
DIBox is an async‑native dependency injection container that uses standard Python type hints to build and manage your service dependency graph automatically. The core philosophy is to remove factory and wiring boilerplate so you can focus on application logic.

DIBox resolves, instantiates, and injects dependencies by following naturally defined type hints in constructors or entry points. It also orchestrates asynchronous startup and safe teardown for resources like database connections, credential loaders, or HTTP clients without extra glue code.

## Key Features
- **Auto-Wiring:** Type-annotated constructors are resolved and injected automatically — no factory boilerplate.
- **Async‑Native:** Async factories, async context managers, and async lifecycle hooks all work out of the box.
- **Lifecycle Management:** Resources start and clean up automatically. DIBox recognizes context managers, generator factories and `start`/`close` conventions.
- **Context-aware `@inject`:** Decorate at import time, resolve at call time from the active container — no container reference at the call site.
- **Flexible Bindings:** Interfaces, instances, sync/async factories, named dependencies, and predicate-based bindings.
- **Resolution Controls:** Permissive, semi-strict, and strict modes control where implicit binding applies; creation policies can allowlist packages and deny specific categories without registering every concrete type.
- **Non‑Invasive:** Works with any class using type hints — third-party SDKs, dataclasses, attrs — no wrappers or base classes required.
- **Modular:** Group bindings into reusable `BindingBox` modules. Compose, override, and share across workers, tests, and entry points.
- **Typed API:** Fully type-annotated — works seamlessly with type checkers and IDE autocompletion.

## QuickStart
DIBox requires almost no setup. Define your classes as usual—whether you use standard Python classes with `__init__`, dataclasses, or attrs models.

### 1. Define your application as usual
Just use type hints to declare dependencies, no DI boilerplate needed.

```python
import asyncio

class Credentials:
    def __init__(self, username: str):
        self.username = username

class Database:
    def __init__(self, creds: Credentials):
        self.creds = creds

class Service:
    def __init__(self, db: Database):
        self.db = db

    async def start(self):
        await asyncio.sleep(0.05)  # simulate warm-up
        print("Service started")

    async def close(self):
        await asyncio.sleep(0.05)  # simulate cleanup
        print("Service closed")

    def run(self):
        print("Service is running...")

```
DIBox detects and manages lifecycle hooks automatically. The `Service` class below uses `start()`/`close()` — one of several supported patterns, covered in full in [Resource Lifecycle](#resource-lifecycle).

### 2. Wire and Run

Only bind what DIBox can't infer — here, `Credentials` because it's a raw value with no type-hinted constructor to follow.

```python
from dibox import DIBox

box = DIBox()
box.bind(Credentials, Credentials(username="admin"))  # raw value: bind it explicitly

async def main():
    async with box:                           # activate container; start() called on managed resources
        service = await box.provide(Service)  # resolve the graph: Credentials → Database → Service
        service.run()
    # close() called automatically on exit

asyncio.run(main())
```

For framework entry points — FastAPI routes, CLI commands — `@inject` is the idiomatic choice. Decoration happens at module load time; resolution happens at call time from whichever container is active:

```python
from dibox import inject, Injected

@inject
async def main(service: Injected[Service]):  # Injected[T] marks the parameter for injection
    service.run()

async def run():
    async with box:   # makes box the active container for this async context
        await main()  # service is resolved and injected automatically

asyncio.run(run())
```

> **Next step:** The quickstart uses permissive mode (the default), where unbound concrete types are automatically created (implicitly self-bound). It keeps concrete graphs low-boilerplate. Use semi-strict or strict mode to control where implicit binding applies, or a deny-all policy to allowlist which types qualify. See [Resolution Modes](#resolution-modes).

## Usage Guide

### Using Decorators for Injection
Decorators allow injecting dependencies into entry points — API routes, CLI commands, Lambda handlers — without cluttering call sites. A key feature: `@inject` rewrites the function's runtime signature, removing `Injected[T]` parameters. Frameworks that inspect signatures at import/routing time only see your "real" parameters (path/query args, request objects, etc.).

DIBox offers three options in increasing order of explicitness.

#### 1. `@inject` — context-based (idiomatic)

The recommended default. Apply `@inject` at module level — no container reference needed at decoration time. At call time, it resolves dependencies from whichever `DIBox` is active via `async with box:`. Because the active container is stored in a `ContextVar`, it is isolated per async task and per OS thread — there is no process-wide global, and concurrent requests each see their own container.

```python
from dibox import inject, Injected

@inject
async def get_report(report_id: str, svc: Injected[ReportService]) -> Report:
    return await svc.fetch(report_id)
```

This pairs naturally with framework lifespans. The `async with box:` that starts your container also establishes the injection context for all `@inject`-decorated functions:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dibox import DIBox, inject, Injected

box = DIBox()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with box:
        box.bind(Database, await create_database())
        yield  # app runs here; @inject resolves from box

app = FastAPI(lifespan=lifespan)

@app.get("/report/{report_id}")
@inject
async def get_report(report_id: str, db: Injected[Database]):
    return await db.fetch_report(report_id)
```

FastAPI sees `get_report(report_id: str)` — the injected `db` parameter is invisible to the framework.

#### 2. `@box.inject` — explicit container

When you want injection tied to a specific container instance rather than the active context, use `@box.inject`. Unlike `@inject`, it ignores the ContextVar entirely — the container is captured at decoration time and always used, regardless of which container is active at call time.

```python
local_box = DIBox()

@local_box.inject
async def specific_handler(service: Injected[Service]):
    ...
```

Useful when you have multiple concurrent containers, in integration tests where you want injection to be explicit, or when you simply prefer the container reference visible at the call site.

For advanced use cases (custom container resolution strategies, enforcing architectural layers), the underlying `Injector` class is available directly. It accepts either a container instance or a `container_resolver` callable and exposes the same `.inject` decorator.

#### Imperative entrypoints (planned)

The entrypoints ADR also proposes `DIBox.call()` and `DIBox.partial()` for direct execution use cases (injecting by inspecting the function signature without `Injected[...]` markers). These APIs are not implemented yet (currently, `DIBox.call()` raises `NotImplementedError`).

Today, the supported imperative API is `await box.provide(T)` (and `box.get(T)` for already-created instances).

### Resource Lifecycle

DIBox acts as the coordinator for resource startup and teardown. All managed instances are started when first provided and torn down in reverse order (LIFO) when the container exits:

```python
async with box:
    setup_bindings(box)
    await run()
# All managed resources are torn down here, in reverse order of creation
```

#### Class-based resources

For class instances, DIBox detects lifecycle hooks automatically after construction. The detection priority is:

1. **Async context manager** (`__aenter__`/`__aexit__`)
2. **Sync context manager** (`__enter__`/`__exit__`)
3. **`start`/`close`/`aclose` convention** — sync or async, detected by name

```python
class DatabaseClient:
    async def start(self):
        self.conn = await engine.connect()

    async def close(self):
        await self.conn.close()

# DIBox calls start() after construction and close() on container exit
db = await box.provide(DatabaseClient)
```

#### Factory-based teardown

When setup and teardown belong together, generator factories keep them co-located. DIBox injects the yielded value and runs the post-yield code when the container exits.

```python
from contextlib import contextmanager, asynccontextmanager

@contextmanager
def create_db_session(engine: Engine) -> Iterator[Session]:
    session = engine.connect()
    try:
        yield session
    finally:
        session.close()

@asynccontextmanager
async def create_http_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=settings.api_url) as client:
        yield client

box.bind(Session, create_db_session)
box.bind(httpx.AsyncClient, create_http_client)
```

Plain generator functions (without the decorator) are also accepted — DIBox wraps them automatically — but the explicit decorator is recommended for clarity.

### Binding Patterns
DIBox shines when you need precise control over object creation. You can mix and match these patterns to handle everything from cloud clients to dynamic configuration.

#### Binding Interfaces & Instances
You can bind a base class to a concrete implementation or a specific instance.

```python
from dibox import DIBox

box = DIBox()

azure_credentials = DefaultAzureCredential()
# Any request for TokenCredential will receive azure_credentials object
# box.bind(TokenCredential, azure_credentials) works too!
box.bind(TokenCredential, instance=azure_credentials)
# Or bind an interface to a concrete class
box.bind(DatabaseInterface, CosmosDBDatabase)
```

#### Factory Functions
Sometimes a simple constructor isn't enough—you may need asynchronous setup (fetching secrets, warming a client) or a third‑party initialization step. Bind the target type to a factory function—sync or async.

Key Feature: DIBox inspects your factory’s signature, auto‑injects its parameters, and if it is `async` it awaits it automatically before wiring downstream dependencies.

```python
# Async factory: simulate secret fetch / remote handshake
async def create_cosmos_client(settings: Settings) -> CosmosClient:
    await asyncio.sleep(0.05)  # simulate IO
    return CosmosClient(url=settings.url, key=settings.key)

# Sync factory depending on the async-created client
def create_orders_container(client: CosmosClient) -> OrderContainer:
    return OrderContainer(client.get_container("orders"))

# Bind factories (DIBox auto-injects Settings, awaits async factory)
box.bind(CosmosClient, create_cosmos_client)
# to be more explicit, you can use the factory= keyword argument:
box.bind(OrderContainer, factory=create_orders_container)

order_container = await box.provide(OrderContainer)  # auto sequence:
# Settings -> await create_cosmos_client -> create_orders_container
```

#### Named dependencies
If you need multiple instances of the same type (like two different storage containers), use the name parameter. DIBox matches this binding to the argument name.

```python
box.bind(ContainerClient, "users", factory=create_users_container)
box.bind(ContainerClient, "orders", factory=create_orders_container)

class DataService:
    def __init__(self, users: ContainerClient, orders: ContainerClient):
        self.users = users    # Injected with "users" binding
        self.orders = orders  # Injected with "orders" binding

# Requesting DataService will get both ContainerClients injected correctly
data_service = await box.provide(DataService)
```

#### Dynamic Predicate-Based Binding
For repeatable patterns, you can use a predicate function to match types dynamically. This is useful for generic loaders or handlers. The factory function can also receive the requested type as a parameter for more context-aware creation.

```python
def load_settings(t: type) -> object:
    # Load settings based on type t
    ...

# Bind ANY type ending in 'Settings' to the 'load_settings' function
box.bind(lambda t: t.__name__.endswith("Settings"), load_settings)

# Now requesting AppSettings or DBSettings will use load_settings automatically
app_settings = await box.provide(AppSettings)
db_settings = await box.provide(DBSettings)
```

#### Resolution Modes

DIBox supports three resolution modes, set at construction time:

```python
box = DIBox()                    # permissive (default)
box = DIBox(mode="semi-strict")  # semi-strict
box = DIBox(mode="strict")       # strict
```

What changes is _implicit self-binding_: whether the container is allowed to treat an unbound concrete type as its own factory when no `bind()` entry exists for it.

- **Permissive (default)** — an unbound concrete type may be implicitly self-bound without an explicit `bind()`, subject to the implicit creation policy. The default policy blocks common primitive/value leaves such as `str`, `int`, and `Path`. The QuickStart examples use this mode. It keeps concrete graphs low-boilerplate; use a deny-all policy to restrict eligibility to owned packages without registering each type.

- **Semi-strict** — declare which types are owned resolution roots with `bind()`; the container implicitly self-binds their concrete transitive dependencies. Ownership is explicit at the boundary — where it matters — without requiring pre-registration of every interior implementation detail.

- **Strict** — every type in the dependency graph must be explicitly registered. Implicit self-binding is disabled: the container raises an error for any unbound type. Use it when you want exhaustive, registry-level visibility over every type the container may resolve.

Types that cannot be inferred — interfaces, external values, and raw parameters — always need explicit bindings. Implicit self-binding only fills in concrete services with no configuration decisions.

##### Semi-strict example

```python
box = DIBox(mode="semi-strict")

box.bind(AppConfig, instance=load_config())          # external value — always explicit
box.bind(StorageClient, S3StorageClient)             # interface → implementation
box.bind_many(AuthService, ReportService)  # root services; transitive concrete deps implicitly self-bound
```

##### Strict example

```python
box = DIBox(mode="strict")

box.bind(AppConfig, instance=load_config())          # external value
box.bind(StorageClient, S3StorageClient)             # interface → implementation
box.bind_many(Database, AuthService, ReportService)  # every concrete type must be declared
```

`bind(T)` registers one self-binding. `bind_many(...)` is shorthand for registering several bindings at once; behavior is the same as calling `bind(...)` repeatedly.

##### Controlling implicit creation

Resolution mode decides where implicit self-binding may happen: at roots and dependencies, only at dependencies, or nowhere. Where the mode permits it, the implicit creation policy decides which unbound concrete types qualify.

The policy evaluates each type in this order:

1. A matching deny rule denies it.
2. Otherwise, a matching allow rule allows it.
3. If no rule matches, the configured guard decides.

In short, deny rules take precedence over allow rules, and matching rules take precedence over the guard. The `"deny-all"` guard is therefore a fallback, not a deny rule: it denies only types that matched no allow rule. This turns allow rules into a strict allowlist without requiring every concrete graph type to be registered.

Rules can match packages and their subpackages, exact types, or custom predicates. This example allows application-owned types while requiring explicit bindings for Pydantic DTOs:

```python
from dibox import DIBox, ImplicitCreationPolicy
from pydantic import BaseModel

policy = ImplicitCreationPolicy(guard="deny-all")
policy.allow_package("my_app")
policy.deny_if(
    lambda type_to_check: issubclass(type_to_check, BaseModel),
    name="Pydantic DTOs",
)

box = DIBox(implicit_creation_policy=policy)
```

The result is:

- Other types in `my_app` match the package allow rule and are allowed before the guard runs.
- Pydantic models in `my_app` match both rules but are denied because deny rules come first.
- Types outside `my_app` match neither rule and are denied by the `"deny-all"` guard.
- Explicit bindings bypass the policy, allowing intentional exceptions for any denied type.

The other guards are `"value-types"` (the default), which blocks common primitive and value types; `"zero-dependency"`, which blocks types without required constructor parameters; and `"none"`, which allows every unmatched concrete type.

Combine this policy with permissive mode when allowlisted types may be resolution roots, or semi-strict mode when roots should still be explicitly bound. Strict mode disables implicit self-binding entirely and therefore does not consult the policy.

### Binding Modules

A `BindingBox` is a portable set of binding rules. Define it once, compose it wherever that context is needed — a pipeline stage, a background worker, a CLI command, a test.

#### Organizing bindings by feature

```python
# storage/deps.py
from dibox import BindingBox

storage_bindings = BindingBox()
storage_bindings.bind(StorageClient, S3StorageClient)
storage_bindings.bind(BlobIndex)
```

```python
# ml/deps.py
from dibox import BindingBox

ml_bindings = BindingBox()
ml_bindings.bind(ModelRegistry)
ml_bindings.bind(Classifier)
```

```python
# main.py
from dibox import DIBox
from storage.deps import storage_bindings
from ml.deps import ml_bindings

async with DIBox() as box:
    box.bind(AppConfig, instance=load_config())  # raw config — bound directly
    box.add_bindings(storage_bindings)
    box.add_bindings(ml_bindings)

    classifier = await box.provide(Classifier)
```

#### Reusing modules across contexts

A `BindingBox` holds binding *rules*, not live resources — it's a plain Python object, independent of any specific container. The same module can be composed into different containers in different contexts without duplication, and because it carries no open connections or handles, it can be imported in any process. This makes it the natural contract between an orchestrator and its workers.

To make this concrete, here's a pipeline stage running as a [Ray](https://www.ray.io/) remote function — a function dispatched to a separate worker process by the framework.

Without modules, every worker duplicates the same setup:

```python
# pipeline/stages.py — defined once, importable from anywhere
enhance_bindings = BindingBox()
enhance_bindings.bind(GPUContext)
enhance_bindings.bind(Enhancer)
```

```python
@ray.remote  # runs this function in a separate worker process
def enhance_v1(config: AppConfig, tiles: list[bytes]) -> list[bytes]:
    async def _run() -> list[bytes]:
        box = DIBox()
        box.bind(AppConfig, instance=config)
        box.bind(GPUContext)  # repeated in every worker
        box.bind(Enhancer)    # and again here
        async with box:
            enhancer = await box.provide(Enhancer)
            return await enhancer.enhance(tiles)
    return asyncio.run(_run())
```

With modules, the worker declares what context it needs in one line:

```python
@ray.remote  # runs this function in a separate worker process
def enhance_v2(config: AppConfig, tiles: list[bytes]) -> list[bytes]:
    async def _run() -> list[bytes]:
        box = DIBox()
        box.bind(AppConfig, instance=config)
        box.add_bindings(enhance_bindings)  # same module — no duplication
        async with box:
            enhancer = await box.provide(Enhancer)
            return await enhancer.enhance(tiles)
    return asyncio.run(_run())
```

The same module also works in-process — for example, as a scoped stage container in the main pipeline:

```python
async with DIBox(parent=run_box) as stage:
    stage.add_bindings(enhance_bindings)
    enhancer = await stage.provide(Enhancer)
    tiles = await enhancer.enhance(tiles)
# GPUContext released when the stage exits
```

#### Overriding bindings for tests

When modules are composed, the last registered wins. This is useful for integration tests: register the production modules first, then add a module with fakes on top without touching the original module.

```python
# tests/fakes.py
fake_storage = BindingBox()
fake_storage.bind(StorageClient, InMemoryStorageClient)  # no S3 in tests

# tests/test_classifier.py
async def test_classifier():
    async with DIBox() as box:
        box.bind(AppConfig, instance=test_config)
        box.add_bindings(ml_bindings)      # real ML module
        box.add_bindings(fake_storage)     # replaces S3StorageClient — last wins

        classifier = await box.provide(Classifier)
        ...
```

#### Resolution order

When the same type is bound in multiple places, **last registered wins**: container's own `bind()` calls always take highest precedence, then modules in reverse registration order.
If no binding matches at all, DIBox can fall back to using the requested type as its own factory — this is what makes `await box.provide(SomeService)` work without an explicit `box.bind(SomeService)`. Permissive mode allows this at roots and dependencies, semi-strict restricts it to transitive dependencies, and strict disables it. In the first two modes, the implicit creation policy can further restrict eligible types. See [Resolution Modes](#resolution-modes).

## Why use DIBox?
### The Power of Auto-Wiring
Dependency Injection (DI) decouples your high-level business logic from low-level implementation details (like database drivers or API clients). This makes your code modular and effortless to test—you can easily swap a real database for a mock during unit tests.

However, traditional DI often trades one problem for another: Dependency Hell. You end up writing hundreds of lines of "glue code" just to instantiate your service graph.

DIBox's standout feature is its ability to automatically resolve and inject dependencies based on type hints. It inspects your classes, sees what they need, and assembles the puzzle for you. You stop writing factories and start writing features.

### Comparison with Other Frameworks
There are many great DI frameworks for Python out there. Here is why you might choose DIBox:
- **vs. Manual Dependency Injection**
  - **The Problem:** Manually instantiating services (Service(Database(Config()))) works for small scripts but becomes tedious and error-prone as your app grows.
  - **The DIBox Way:**  DIBox eliminates boilerplate factory code by auto-wiring based on type hints. You write less glue code and focus on your business logic.

- **vs. [dependency-injector](https://python-dependency-injector.ets-labs.org/)**
  - **The Approach:** Dependency Injector is a powerful, feature-rich framework that uses a declarative style. You explicitly define Container classes and Providers for every component.
  - **The DIBox Difference:** DIBox takes a more implicit, convention-over-configuration approach. You rarely need to define explicit providers—most wiring is automatic based on type hints. This makes it particularly seamless when integrating Third-Party SDKs (like Azure SDK or Boto3). You can simply bind an abstract class (e.g., TokenCredential) to a concrete instance, and DIBox automatically injects it into the SDK client's constructor without needing wrapper classes or complex factory providers.

- **vs. [Injector](https://injector.readthedocs.io/en/latest/)**
    - **The Approach:** Injector encourages a structured configuration style using explicit **Module** classes and **Provider** methods. While it supports type hints, it often relies on the `@inject` decorator to explicitly mark constructors for injection—particularly when you need to mix injectable and non-injectable arguments or when auto_bind is disabled.
    - **The DIBox Difference:** DIBox favors a zero-boilerplate approach. It does not require separate Module definitions to wire your graph; it defaults to auto-wiring based on existing type hints. For lifecycle concerns, DIBox automatically detects common async/sync resource hooks (`__aenter__`/`__aexit__`, `start()`/`close()`, context managers) and runs them for you. Injector provides lifecycle and scoping control through its own mechanisms and explicit patterns; DIBox emphasizes convention and automatic detection for asynchronous workloads.

- **vs. [Punq](https://bobthemighty.github.io/punq/)**
    - **The Approach:** Punq is a minimalistic DI container that shares our philosophy of simplicity and auto-wiring. It relies heavily on explicit bindings and does not support advanced features like async lifecycle management or predicate-based bindings.
    - **The DIBox Difference:** DIBox adds async lifecycle management and a few more binding patterns while keeping the same “type-hints-first” feel.

- **vs. [Dishka](https://dishka.readthedocs.io/en/latest/)**
  - **The Approach:** Dishka is a powerful DI framework built around a first-class scoping system and explicit `Provider` classes. This gives you fine-grained control over dependency lifetimes and structure, with ready-made integrations for many popular frameworks.
  - **The DIBox Difference:** DIBox offers a simpler, more minimal API. Instead of `Provider` classes, DIBox auto-wires any class with a type-annotated constructor, so you only bind what can't be inferred (e.g., interfaces, raw values). This convention-over-configuration approach reduces boilerplate for common cases. DIBox also offers unique features like predicate-based binding and named-argument injection. However, Dishka currently has a more mature feature set, including a robust scoping model and a dependency graph visualizer. If those features are critical for your project right now, Dishka is an excellent choice. Scopes are on the DIBox roadmap.

- **vs. [FastAPI's Depends](https://fastapi.tiangolo.com/tutorial/dependencies/)**
  - **The Approach:** FastAPI revolutionized Python development with its intuitive, type-hint-based dependency injection. It is the primary inspiration behind DIBox. FastAPI's dependency injection system is tightly integrated with its web framework. It uses the `Depends` marker to declare dependencies in path operation functions.
  - **The DIBox Difference:** While FastAPI's DI is excellent for web applications, DIBox is a standalone framework that can be used across any Python application. It extends the same principles to a broader context, including CLI apps, serverless functions, and background services. DIBox also adds advanced features like async lifecycle management and predicate-based bindings that go beyond FastAPI's capabilities.

## Contributing
The project is in early stages, and contributions are welcome! Please contact me (Alex Z.) via [GitHub issues](https://github.com/mxAlexZ/dibox/issues), [LinkedIn](https://www.linkedin.com/in/alex-zee/) or [email](mailto:alex.zee@outlook.cz) for any questions, suggestions, or contributions.
The source code is hosted both on GitHub (https://github.com/mxAlexZ/dibox) and GitLab (https://gitlab.com/AlexZee/dibox). The actual development happens on GitLab, while GitHub is used for better visibility.
