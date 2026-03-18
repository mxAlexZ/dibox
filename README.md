
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
- [Advanced usage](#advanced-usage)
  - [Using Decorators for Injection](#using-decorators-for-injection)
  - [Resource Lifecycle](#resource-lifecycle)
  - [Advanced Binding Patterns](#advanced-binding-patterns)
    - [Binding Interfaces & Instances](#binding-interfaces--instances)
    - [Factory Functions](#factory-functions)
    - [Named dependencies](#named-dependencies)
    - [Dynamic Predicate-Based Binding](#dynamic-predicate-based-binding)
  - [Binding Modules](#binding-modules)
    - [Organizing bindings by feature](#organizing-bindings-by-feature)
    - [Reusing modules across contexts](#reusing-modules-across-contexts)
    - [Overriding bindings for tests](#overriding-bindings-for-tests)
    - [Resolution order](#resolution-order)
- [Why use DIBox?](#why-use-dibox)
  - [The Power of Auto-Wiring](#the-power-of-auto-wiring)
  - [Comparison with Other Frameworks](#comparison-with-other-frameworks)
    - [vs. Manual Dependency Injection](#vs-manual-dependency-injection)
    - [vs. dependency-injector](#vs-dependency-injector)
    - [vs. Injector](#vs-injector)
    - [vs. Punq](#vs-punq)
    - [vs. Dishka](#vs-dishka)
    - [vs. FastAPI's Depends](#vs-fastapis-depends)
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
- **Easy to Adopt:** Minimal concepts and minimal binding for most internal code.
- **Pragmatic Auto-Wiring:** If a class can be constructed based on type hints, DIBox will build it. This convention-first approach eliminates nearly all factory boilerplate for your internal services.
- **Async‑Native Core:** Seamlessly injects into async call chains and supports async factories out of the box.
- **Lifecycle Automation:** Resources start and clean up automatically. DIBox recognizes context managers (including generator-based factories) and `start`/`close` conventions.
- **Advanced Binding Options:** Supports predicate bindings, named injections, factory functions (with auto‑injected factory parameters), and modular binding organization.
- **Non‑Invasive:** Works with any class using type hints—including third-party SDKs, dataclasses, and attrs — no wrappers or base classes required.
- **Context-aware `@inject`:** Decorate entry points at import time, activate a container with `async with box:`, and `@inject` resolves dependencies from that context at call time. No container reference at the call site, no per-function wiring.
- **No Global State Required:** Works equally well with local container instances — no hidden singletons, easy to isolate in unit tests.
- **Two resolution styles:** Declarative decorators (`@inject`, `@box.inject`) provide signature-aware, import-time integration for frameworks; imperative `box.provide(...)` gives direct runtime control.
- **Typed API:** The public API is strictly type-annotated, so it works well type checkers and IDE autocompletion.

## QuickStart
DIBox requires almost no setup. Define your classes as usual—whether you use standard Python classes with `__init__`, dataclasses, or attrs models.

### 1. Define your application as usual
DIBox detects and manages lifecycle hooks automatically. The `Service` class below uses `start()`/`close()` — one of several supported patterns, covered in full in [Resource Lifecycle](#resource-lifecycle).

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

### 2. Wire and Run
We only bind `Credentials` manually because it is raw data. DIBox automatically figures out how to create `Database` and inject it into `Service`.

The only wiring you need to do is tell DIBox how to create the things it can’t infer on its own (like `Credentials`)

```python
def setup_bindings(box: DIBox):
    box.bind(Credentials, Credentials(username="admin"))
```

To get a service instance, you can call `provide()` with the target type. DIBox will inspect the constructor, see that it needs a `Database`, then see that `Database` needs `Credentials`, and automatically build the whole graph for you.

```python
box = DIBox()

async def run():
    # DIBox creates Credentials -> Database -> Service + awaits start()
    service = await box.provide(Service)
    service.run()
```

The idiomatic alternative is `@inject`. Frameworks like FastAPI and Typer collect entry points at import time — before your application starts — so decorators must be applied before any container exists. `@inject` is designed for this: the decorator is applied at module load time, and dependencies are resolved only when the function is actually called, from whichever container is active in the current context.

"Active in the current context" means the container entered with `async with box:` in the current async task or thread. It is not a process-wide global — concurrent requests each see their own container — so `@inject` is safe to use in parallel execution.

Parameters annotated with `Injected[...]` are resolved automatically and removed from the visible signature, which is important when frameworks like FastAPI or Typer inspect signatures at import time.

```python
from dibox import inject, Injected

@inject  # applied at module level — no container reference needed
async def run(service: Injected[Service]):
    service.run()
```

Finally, activate the container with `async with` and call your entry point:

```python
async with box:
    setup_bindings(box)
    await run()  # service is resolved from box
# When the `async with` block exits, DIBox automatically calls `close()`
# on the `Service` instance and any other managed resources, ensuring
# safe and predictable cleanup.
```

That's the core loop: bind the bits DIBox can't infer, activate the container with `async with box:`, and `@inject` handles the rest.

## Advanced usage

### Using Decorators for Injection
Decorators allow injecting dependencies into entry points — API routes, CLI commands, Lambda handlers — without cluttering function signatures. A key feature is **signature modification**: injected parameters are removed from the visible signature, so frameworks like FastAPI or Typer don't see them when generating API docs or CLI help text.

DIBox offers three options in increasing order of explicitness.

#### 1. `@inject` — context-based (idiomatic)

The recommended default. Apply `@inject` at module level — no container reference needed at decoration time. At call time, it resolves dependencies from whichever `DIBox` is active via `async with box:`.

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

When you want injection tied to a specific container instance rather than the active context, use `@box.inject`. The container is captured at decoration time.

```python
local_box = DIBox()

@local_box.inject
async def specific_handler(service: Injected[Service]):
    ...
```

Useful when you have multiple concurrent containers, in integration tests where you want injection to be explicit, or when you simply prefer the container reference visible at the call site.

#### 3. `Injector` — reusable policy

`Injector` is for cases where you want one injection policy object applied consistently across many entry points. Create it once, use `@injector.inject` everywhere.

```python
from dibox import DIBox, Injected, Injector
import azure.functions as func

app_box = DIBox()
api_injector = Injector(app_box)

class ProcessingService:
    def process(self, body: str) -> str:
        return f"Processed: {body}"

# The framework sees: main(req: func.HttpRequest)
@api_injector.inject
async def main(req: func.HttpRequest, service: Injected[ProcessingService]) -> func.HttpResponse:
    result = service.process(req.get_body().decode())
    return func.HttpResponse(f"Success! {result}", status_code=200)
```

`Injector` also accepts `container_resolver` for late-bound or scoped containers:

```python
# Equivalent to @inject — resolves from the active context
session_injector = Injector(container_resolver=DIBox.from_context)
```

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

### Advanced Binding Patterns
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

When the same type is bound in multiple places, **last registered wins**: container's own `bind()` calls always take highest precedence, then modules in reverse registration order. If no binding matches at all, DIBox falls back to using the requested type as its own factory — this is what makes `await box.provide(SomeService)` work without an explicit `box.bind(SomeService)`.

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
