
# DIBox

[![release](https://gitlab.com/AlexZee/dibox/-/badges/release.svg)](https://gitlab.com/AlexZee/dibox/-/releases) ![Python Versions](https://img.shields.io/pypi/pyversions/dibox) [![coverage](https://gitlab.com/AlexZee/dibox/badges/main/coverage.svg)](https://gitlab.com/AlexZee/dibox/-/commits/main) [![PyPI - License](https://img.shields.io/pypi/l/dibox)](https://gitlab.com/AlexZee/dibox/-/blob/main/LICENSE)

---

**⚠️ Project Status: Early Development**

This library is in its early stages. The design and API are not yet fully established and may change significantly in future releases. Feedback, suggestions, and contributions are very welcome!

---

DIBox is an async-native dependency injection container for Python. It builds and manages object graphs from standard type hints, removing factory and wiring boilerplate.

Concrete classes can be constructed automatically; explicit bindings supply configuration, choose implementations, or define factories. DIBox also coordinates startup and reverse-order teardown for managed resources.

- [Installation](#installation)
- [Key Features](#key-features)
- [QuickStart](#quickstart)
- [Usage Guide](#usage-guide)
    - [Using Decorators for Injection](#using-decorators-for-injection)
    - [Resource Lifecycle](#resource-lifecycle)
    - [Binding Patterns](#binding-patterns)
    - [Missing-Binding Policy](#missing-binding-policy)
    - [Binding Modules](#binding-modules)
- [Why use DIBox?](#why-use-dibox)
- [Contributing](#contributing)

## Installation
```
pip install dibox
```

Requires Python 3.11+.

## Key Features
- **Auto-Wiring:** Type-annotated constructors are resolved and injected automatically — no factory boilerplate.
- **Async‑Native:** Async factories, async context managers, and async lifecycle hooks all work out of the box.
- **Lifecycle Management:** Resources start and clean up automatically. DIBox recognizes context managers, generator factories and `start`/`close` conventions.
- **Context-aware `@inject`:** Decorate at import time, resolve at call time from the active container — no container reference at the call site.
- **Flexible Bindings:** Interfaces, instances, sync/async factories, named dependencies, and predicate-based bindings.
- **Missing-Binding Policy:** Choose whether unbound roots and dependencies may be created implicitly, with allow and deny rules for trusted types and packages.
- **Non‑Invasive:** Works with any class using type hints — third-party SDKs, dataclasses, attrs — no wrappers or base classes required.
- **Modular:** Group bindings into reusable `BindingBox` modules. Compose, override, and share across workers, tests, and entry points.
- **Typed API:** Fully type-annotated — works seamlessly with type checkers and IDE autocompletion.

## QuickStart
DIBox requires almost no setup. Define your classes as usual — whether you use standard Python classes with `__init__`, dataclasses, or attrs models.

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

DIBox detects and manages lifecycle hooks automatically. `Service` uses `start()`/`close()` — one of several supported patterns covered in [Resource Lifecycle](#resource-lifecycle).

### 2. Wire and Run

Only bind what DIBox can't infer — here, a configured `Credentials` instance because DIBox should not invent a value for its `username: str` parameter.

```python
from dibox import DIBox

box = DIBox()
box.bind(Credentials, Credentials(username="admin"))  # configured instance: bind it explicitly


async def main():
    async with box:  # activate the container
        service = await box.provide(Service)  # build the graph and call Service.start()
        service.run()
    # Service.close() is called automatically on exit


asyncio.run(main())
```

The binding supplies the configured `Credentials`. With the default `"open"` policy, DIBox infers how to construct `Database` and `Service` from their constructor annotations.

For framework entry points — FastAPI routes, CLI commands — `@inject` is the idiomatic choice. Decoration happens at module load time; resolution happens at call time from whichever container is active:

```python
from dibox import DIBox, Injected, inject

app_box = DIBox()
app_box.bind(Credentials, Credentials(username="admin"))


@inject  # Injected[T] marks the parameter for injection
async def run_service(service: Injected[Service]):
    service.run()


async def run():
    async with app_box:  # make app_box active in this async context
        await run_service()  # resolve and inject Service automatically


asyncio.run(run())
```

> **Next step:** The quickstart uses the default `"open"` policy, where eligible unbound concrete types are created automatically. Use `"explicit-roots"` to declare the container's entrypoints while retaining inferred internals, or `"closed"` to require allow rules for inferred dependencies. See [Missing-Binding Policy](#missing-binding-policy).

## Usage Guide

### Using Decorators for Injection
Decorators allow injecting dependencies into entry points — API routes, CLI commands, Lambda handlers — without cluttering call sites. A key feature: `@inject` rewrites the function's runtime signature, removing `Injected[T]` parameters. Frameworks that inspect signatures at import/routing time only see your "real" parameters (path/query args, request objects, etc.).

DIBox offers two options with different container-selection behavior.

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
box.bind(Database, factory=create_database)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with box:
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

#### Missing-Binding Policy

When no binding matches a concrete class, DIBox can use the class itself as a factory and follow its constructor annotations. The missing-binding policy controls where this implicit creation is allowed:

```python
box = DIBox()                         # "open" (default)
box = DIBox(policy="explicit-roots")
box = DIBox(policy="closed")
```

- **`"open"`** — eligible unbound roots and transitive dependencies are created implicitly. This is the zero-configuration path used throughout the QuickStart.
- **`"explicit-roots"`** — a direct request must have a binding, but eligible unbound dependencies inside that accepted graph are still created implicitly. This makes the container's entrypoints explicit without registering every implementation detail.
- **`"closed"`** — direct requests must have bindings, and unbound transitive dependencies must match an allow rule. This limits inferred construction to trusted types and packages.

Common value types such as `str`, `int`, and `Path` are not created implicitly by default. Interfaces, external values, and constructor parameters that express configuration choices also need explicit bindings. An explicit binding always bypasses the missing-binding policy because it already records construction intent.

With explicit roots, bind the services that callers may request directly and let their concrete internals follow constructor annotations:

```python
box = DIBox(policy="explicit-roots")

box.bind(AppConfig, instance=load_config())  # external value
box.bind(StorageClient, S3StorageClient)     # interface → implementation
box.bind_many(AuthService, ReportService)    # accepted request roots

report_service = await box.provide(ReportService)
```

`bind_many(...)` is shorthand for registering several bindings at once.

For finer control, create a policy object and add rules for exact types, packages and their subpackages, or custom predicates. Deny rules take precedence over allow rules:

```python
from dibox import DIBox, MissingBindingPolicy
from pydantic import BaseModel

policy = MissingBindingPolicy.from_preset("closed")
policy.allow_package("my_app")
policy.deny_if(
    lambda type_to_check: issubclass(type_to_check, BaseModel),
    name="Pydantic DTOs",
)

box = DIBox(policy=policy)
box.bind(AppConfig, instance=load_config())
box.bind(StorageClient, S3StorageClient)
box.bind(ReportService)  # root bindings are still required
```

Here, unbound dependencies defined in `my_app` may be inferred, except Pydantic models. Other unmatched dependencies require an explicit binding. Allow rules do not authorize roots under `"explicit-roots"` or `"closed"`; roots remain visible through their bindings.

Rules can be added with `allow_type()`, `deny_type()`, `allow_package()`, `deny_package()`, `allow_if()`, and `deny_if()`. Configure the policy before the first resolution because compiled dependency graphs are cached.

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

#### Resolution order

Direct container bindings take precedence over module bindings. Among modules, **last registered wins**.
If no binding matches at all, DIBox can fall back to using the requested type as its own factory — this is what makes `await box.provide(SomeService)` work without an explicit `box.bind(SomeService)`. The missing-binding policy controls whether that fallback is available at the request root and for transitive dependencies. See [Missing-Binding Policy](#missing-binding-policy).

## Why use DIBox?
### Infer construction, declare intent

Constructor annotations often contain the complete recipe for building a concrete service. Requiring a registration that merely repeats that recipe adds boilerplate and couples the composition root to every internal class.

When no binding matches, DIBox can derive an implicit self-binding: the requested class becomes its own factory, and its annotated dependencies are resolved recursively. Explicit bindings remain focused on decisions that type hints cannot express — configured values, implementation choices, named variants, custom factories, and accepted request roots.

This inference is governed rather than unconditional. The missing-binding policy independently controls which roots and transitive dependencies DIBox may construct, from an open zero-configuration default to explicit roots and allowlisted internals. The combination of inferred construction and explicit boundaries keeps small graphs simple without giving up control as an application grows.

### Comparison with Other Frameworks
Python has several excellent dependency-injection tools with different priorities. This is a high-level orientation, not a feature benchmark. These projects evolve, so details may become outdated or contain mistakes; consult the linked documentation when choosing a library, and please report corrections.

- **Manual dependency injection** keeps construction explicit and introduces no framework dependency. It is often the clearest choice for small graphs. DIBox becomes useful when recursive assembly, repeated composition, and resource lifecycle coordination start adding glue code.

- **[Dependency Injector](https://python-dependency-injector.ets-labs.org/)** uses explicit containers and providers, with extensive support for configuration, overrides, resources, asynchronous providers, and application wiring. DIBox instead derives eligible concrete bindings from constructor annotations, allowing applications to reserve explicit bindings for choices and boundaries that annotations cannot express.

- **[Injector](https://injector.readthedocs.io/en/latest/)** is a Pythonic, Guice-inspired container with transitive injection, modules, scopes, provider methods, and optional automatic binding of missing types. Regular constructors use `@inject` or `Inject[...]` to identify injectable parameters, while provider callables infer annotated parameters. DIBox does not require markers on constructors and centers async resource lifecycle and missing-binding authorization in the container.

- **[Punq](https://punq.readthedocs.io/en/latest/)** is intentionally small and unintrusive, with constructor injection, explicit registration, transient and singleton scopes, and no decorators or global state. DIBox shares the emphasis on ordinary Python classes while adding async lifecycle management, named and predicate bindings, and policy-governed implicit self-binding.

- **[Dishka](https://dishka.readthedocs.io/en/stable/)** provides first-class scopes, finalization, modular providers, validation, dependency-graph plotting, and integrations with many frameworks. It is a strong choice when rich lifetime modeling and ecosystem integrations are priorities. DIBox takes a smaller constructor-driven approach in which the missing-binding policy can infer concrete internals without provider declarations for each class.

#### Inspiration: FastAPI

[FastAPI](https://fastapi.tiangolo.com/) is a web framework rather than a standalone DI library, but its broader design was the primary inspiration for DIBox: define an endpoint as an ordinary function, describe what it needs through its signature and type hints, and let the framework handle the surrounding plumbing.

DIBox applies the same idea to object construction. Constructors and factories describe their dependencies through ordinary Python signatures, while the container assembles the graph and manages resource lifecycles. This brings FastAPI's signature-driven developer experience to an application-neutral container for web handlers, workers, CLIs, and other entrypoints — including applications built with FastAPI.

## Contributing
The project is in early stages, and contributions are welcome! Please contact me (Alex Z.) via [GitHub issues](https://github.com/mxAlexZ/dibox/issues), [LinkedIn](https://www.linkedin.com/in/alex-zee/) or [email](mailto:alex.zee@outlook.cz) for any questions, suggestions, or contributions.
The source code is hosted both on GitHub (https://github.com/mxAlexZ/dibox) and GitLab (https://gitlab.com/AlexZee/dibox). The actual development happens on GitLab, while GitHub is used for better visibility.
