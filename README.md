# DIBox

Async-native dependency injection framework based on type hints and automatic lifecycle management.

- [Installation](#installation)
- [What is DIBox?](#what-is-dibox)
- [Key Features](#key-features)
- [Quickstart](#quickstart)
  - [1. Define your application as usual](#1-define-your-application-as-usual)
  - [2. Wire and Run](#2-wire-and-run)
- [Advanced usage](#advanced-usage)
  - [Using the @inject Decorator](#using-the-inject-decorator)
  - [Advanced Binding Patterns](#advanced-binding-patterns)
    - [Binding Interfaces & Instances](#binding-interfaces--instances)
    - [Factory Functions](#factory-functions)
    - [Named dependencies](#named-dependencies)
    - [Dynamic Predicate-Based Binding](#dynamic-predicate-based-binding)
- [Why use DIBox?](#why-use-dibox)
  - [The Power of Auto-Wiring](#the-power-of-auto-wiring)
  - [Comparison with Other Frameworks](#comparison-with-other-frameworks)
    - [vs. Manual Dependency Injection](#vs-manual-dependency-injection)
    - [vs. dependency-injector](#vs-dependency-injector)
    - [vs. Injector](#vs-injector)
    - [vs. Punq](#vs-punq)
    - [vs. FastAPI's Depends](#vs-fastapis-depends)

## Installation
```
pip install dibox
```

## What is DIBox?
DIBox is an async‑native, zero‑configuration dependency injection framework that uses standard Python type hints to build and manage your service graph automatically. Inspired by the ergonomics of FastAPI and Typer, it removes factory and wiring boilerplate so you can focus on application logic.

Declare dependencies naturally—in constructors or entry points—and DIBox resolves, instantiates, and injects them on demand. It also orchestrates asynchronous startup and safe teardown: detecting and awaiting common hooks for resources like database connections, credential loaders, or HTTP clients. This lets you fetch secrets, warm clients, and open connections automatically—then shut them down cleanly without extra glue code.

## Key Features
- **Easy to Learn & Use:** No steep learning curve or complex terminology to master. Even for complex projects, explicit binding is minimal since most classes auto‑wire from type hints.
- **Zero‑Config Instantiation:** If a class can be constructed, DIBox will resolve and inject it—no extra configuration required.
- **Async‑Native Core:** Seamlessly injects into async call chains and supports async factories out of the box.
- **Lifecycle Automation:** Detects and runs `start()`/`close()`, or context manager hooks (`__aenter__`/`__aexit__`, `__enter__`/`__exit__`) to manage resources safely.
- **Pure Typing Integration:** Uses standard typing (`Annotated`, `Union`, generics) for resolution—editor friendly and refactor safe.
- **Advanced Binding Options:** Supports predicate bindings, named injections, and factory functions (with auto‑injected factory parameters).
- **Optional Decorators:** `@inject` is convenience only; explicit `await box.provide(...)` stays fully supported for framework integration.
- **No Forced Global State:** A global container exists for convenience, but DIBox works equally well with per‑scope/local instances—ideal for unit tests and isolated runtimes without hidden singletons.
- **Non‑Invasive:** Works with any class using type hints—including third-party SDKs, dataclasses, and attrs — no wrappers or base classes required.

## Quickstart
DIBox requires almost no setup. Define your classes as usual—whether you use standard Python classes with `__init__`, dataclasses, or attrs models.

### 1. Define your application as usual
We define a `Database` that requires asynchronous connection logic. Notice we implement `__aenter__` and `__aexit__`—DIBox will detect these and manage the connection for us automatically. Alternatively, you can implement `start()`/`close()` methods if you prefer.

```python
class Credentials:
    def __init__(self, username: str):
        self.username = username

class Database:
    def __init__(self, creds: Credentials):
        self.creds = creds

    def __enter__(self):
        print(f"Database connected as {self.creds.username}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Database connection closed")

class Service:
    def __init__(self, db: Database):
        self.db = db

    async def start(self):
        await asyncio.sleep(0.05)  # simulate warm-up
        print("Service started")

    def run(self):
        print("Service is running...")

```

### 2. Wire and Run
We only need to bind the Credentials manually because they are raw data. DIBox automatically figures out how to create the Database and inject it into the Service.

Crucially, because we use async with box, the container ensures our database connects before usage and closes safely after exiting the block.

```python
from dibox import DIBox

async def main():
    # 1. Create the container
    async with DIBox() as box:

        # 2. Bind simple core objects
        box.bind(Credentials, Credentials(username="admin"))

        # 3. Request the service
        # DIBox creates Database -> calls __enter__ -> injects into Service -> awaits start()
        service = await box.provide(Service)
        service.run()
    # DIBox automatically called __exit__ on the Database here!

if __name__ == "__main__":
    asyncio.run(main())
```

You have just built a type-safe, async-native application with zero boilerplate. But we are just getting started. DIBox is packed with powerful features to handle complex architectures—including interface binding, factory functions, and optional decorators for your entry points. Ready to see what else it can do? Let's dive in!

## Advanced usage

### Using the @inject Decorator
While strict type-hinting in constructors covers most of your application, you eventually reach the "entry points"—places where a framework (like Azure Functions, AWS Lambda, or a CLI) calls your code.

You can use the @inject decorator here. It inspects your arguments, identifies which ones need injection using the Injected marker, and passes them in automatically.

**Example: Azure Function Handler**

In this scenario, the Azure runtime calls `main` with a `req` object. DIBox intercepts the call, creates your `ProcessingService` (and its dependencies), and injects it alongside the request.

```python
import azure.functions as func
from dibox import inject, Injected

class ProcessingService:
    def process(self, body: str) -> str:
        return f"Processed: {body}"

# The decorator modifies the signature so Azure sees: main(req: func.HttpRequest)
# But DIBox calls it as: main(req, service=instance_of_processing_service)
@inject()
async def main(req: func.HttpRequest, service: Injected[ProcessingService]) -> func.HttpResponse:
    result = service.process(req.get_body().decode())
    return func.HttpResponse(f"Success! {result}", status_code=200)
```

By default, `@inject` uses a convenient `global_dibox` singleton container. You can bind dependencies to it from anywhere in your application.

```python
from dibox import global_dibox, inject, Injected

# You can access global_dibox to bind things manually
global_dibox.bind(APIKey, APIKey("secret_key"))

# Uses global_dibox implicitly
@inject()
def my_handler(service: Injected[Service]):
    ...
```

For greater control, you can pass a dedicated `DIBox` instance to the decorator. This ensures dependency resolution is isolated and predictable.

```python
from dibox import DIBox, inject

# Create a specific container for this app or test
local_box = DIBox()
local_box.bind(APIKey, APIKey("test_key"))

# Pass it explicitly to the decorator
@inject(local_box)
async def specific_handler(service: Injected[Service]):
    ...
```

### Advanced Binding Patterns
DIBox shines when you need precise control over object creation. You can mix and match these patterns to handle everything from cloud clients to dynamic configuration.

#### Binding Interfaces & Instances
You can bind a base class to a concrete implementation or a specific instance.

```python
azure_credentials = DefaultAzureCredential()
# Any request for TokenCredential will receive azure_credentials object
dibox.bind(TokenCredential, azure_credentials)
# Or bind an interface to a concrete class
dibox.bind(DatabaseInterface, CosmosDBDatabase)
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
box.bind(OrderContainer, create_orders_container)

order_container = await box.provide(OrderContainer)  # auto sequence:
# Settings -> await create_cosmos_client -> create_orders_container
```

#### Named dependencies
If you need multiple instances of the same type (like two different storage containers), use the name parameter. DIBox matches this binding to the argument name.

```python
box.bind(ContainerClient, create_users_container, name="users")
box.bind(ContainerClient, create_orders_container, name="orders")

class DataService:
    def __init__(self, users: ContainerClient, orders: ContainerClient):
        self.users = users    # Injected with "users" binding
        self.orders = orders  # Injected with "orders" binding

# Requesting DataService will get both ContainerClients injected correctly
data_service = await box.provide(DataService)
```

#### Dynamic Predicate-Based Binding
For repeatable patterns, you can use a predicate function to match types dynamically. This is useful for generic loaders or handlers.

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
    - **The DIBox Difference:** DIBox offers a richer feature set while maintaining simplicity. Its auto-wiring capabilities, async-native design, and smart lifecycle management set it apart from more basic containers like Punq.

- **vs. [FastAPI's Depends](https://fastapi.tiangolo.com/tutorial/dependencies/)**
  - **The Approach:** FastAPI revolutionized Python development with its intuitive, type-hint-based dependency injection. It is the primary inspiration behind DIBox. FastAPI's dependency injection system is tightly integrated with its web framework. It uses the `Depends` marker to declare dependencies in path operation functions.
  - **The DIBox Difference:** While FastAPI's DI is excellent for web applications, DIBox is a standalone framework that can be used across any Python application. It extends the same principles to a broader context, including CLI apps, serverless functions, and background services. DIBox also adds advanced features like async lifecycle management and predicate-based bindings that go beyond FastAPI's capabilities.