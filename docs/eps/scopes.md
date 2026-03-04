
# Scopes


### Problem Statement:
Real-world applications have dependencies with different lifetimes. A database connection pool should live for the entire application, while request-specific contexts should be created per request. Container nesting creates a hierarchy where parent containers hold long-lived dependencies and children hold short-lived ones. <-- This is more about scoping, container nesting is an additional tool to help with that.

Managing the lifecycle of dependencies is critical. A "scope" defines how long an instance of a dependency should live. For example, a database connection might be a long-lived "singleton," while a request-specific cache might be a short-lived "transient" or "request" scoped object.

## Idea 1: Provide function handling scopes with @inject
To support dynamic, nested scopes with the @inject decorator, DIBox can accept either a DIBox instance or a provider function.
- If the provider is a generator (using yield), the decorator will manage the scope’s lifetime with an async context manager, ensuring proper disposal (ideal for request-scoped containers).
- If the provider is a regular function (using return), the decorator simply borrows the container without managing its lifecycle (ideal for session or global scopes).

```python
# Provider creates and yields a new container for a limited scope.
async def request_container_provider() -> AsyncGenerator[DIBox, None]:
    async with DIBox() as box:  # New container for the request scope
        box.bind(RequestID, to=lambda: f"req-{random.randint(100, 999)}")
        yield box
    # Container is automatically closed here.

def session_container_provider(request: Request) -> DIBox:
    # Reuse a long-lived container for the session scope
    box = session_boxes.get(request.session_id)
    return box

# @inject manages the container's lifecycle from the provider.
# each handle_request call gets a new, isolated container.
@inject(request_container_provider)
async def handle_request(request_id: Injected[RequestID]):
    print(f"Handling request with ID: {request_id}")

# @inject passes non-injectable arguments (like request) to the provider function.
@inject(session_container_provider)
async def handle_session(request: Request, session_data: Injected[SessionData]):
    print(f"Handling session {request.session_id} with data: {session_data}")
    # session_data is resolved from the reused session container
```
Challenge:
- This design introduces complexity in the @inject decorator - handling yield/return, managing arguments for the provider function.
- May confuse users about when scopes are created and disposed.
- Complicates optimization strategies - how to cache injected arguments?

Note: Transient scope can be made explicit by providing another decorator or parameter to @inject instead of inspecting yield vs return.

## Idea 2: Declarative Scopes via Decorators (ASP.NET Core style)
In this model, the class itself declares its intended scope using a decorator. The container reads this metadata and manages the instance accordingly.
```python
@dibox.singleton
class AppConfig: ...

@dibox.scoped # Lives for the duration of the current scope (e.g., request)
class RequestHandler: ...

@dibox.transient # A new instance is created every time
class NotificationClient: ...

# The container automatically respects these decorators
config1 = await box.provide(AppConfig)
config2 = await box.provide(AppConfig) # Same instance
```

Challenge: This couples the component to the DI framework. This goes against the original phylosophy of non-invasive design. Meaning of scopes may vary between applications, leading to confusion; only singleton and transient are universally understood. Custom scopes would require additional decorators or parameters, complicating the API.

## Idea 3: Provider-Defined Scopes (Guice/Dishka style)
Here, the scope is specified during the binding process.

```python
# Bindings define the scope
box.bind(AppConfig, scope="singleton")
box.bind(RequestHandler, scope="request")
box.bind(NotificationClient, scope="transient") # Default

# The container uses the binding's scope to manage instances
handler1 = await request_scope.provide(RequestHandler)
handler2 = await request_scope.provide(RequestHandler) # Same instance within the scope
```
Challenge: This introduces a new scope parameter to the bind method and requires the container to be aware of different scope contexts (e.g., what does "request" mean?). How are these scopes created and managed?


## Container Nesting

Benefits:
- **Hierarchical scopes:** Natural mapping to app → request lifetimes
- **Isolation:** Children can have bindings without polluting the parent
- **Dependency overriding:** Children can replace parent bindings (e.g., mocks for testing) without affecting the parent.

```python
# Application-level container (long-lived)
app_box = DIBox()
app_box.bind(Config, prod_config)
app_box.bind(DatabasePool, create_pool)

# Request-level container (short-lived, per-request)
async with DIBox(parent=app_box) as request_box:
    request_box.bind(RequestContext, RequestContext(request.id))
    service = await request_box.provide(RequestContext)
    config = await request_box.provide(Config)  # Inherited from app_box
```

A child container could inherit bindings from a parent, enabling shared dependencies (like a global `Config`) while allowing overrides.

### Where are instances created?
- if the parent has a binding for `DatabasePool`, but has not created an instance yet, should the child keep it or the parent?
- auto-wired and explicitly bound instances by a child container should be owned by the child.

### Lifecycle and ownership
**Challenge:** How are lifecycles managed across nested containers? If a parent is closed, what happens to children? This could complicate the async context management.

**Suggested approach:** Each container manages only its own instances - if a parent container is aware of its children, it can close them when it is closed, but it would create cyclic dependencies.
Children reference parents for resolution but don't create bidirectional ownership. If a child outlives its parent, that's a usage error.

### Override semantics
```python
app_box.bind(PaymentGateway, RealPaymentGateway)
gateway1 = await app_box.provide(PaymentGateway)  # RealPaymentGateway

async with DIBox(parent=app_box) as test_box:
    test_box.bind(PaymentGateway, MockPaymentGateway)  # Override
    gateway2 = await test_box.provide(PaymentGateway)  # MockPaymentGateway
```

**Rule:** Child overrides are local and don't affect the parent or siblings.

### parent.create_child() vs. DIBox(parent=...) Decision
- Constructor-based approach avoids cyclic dependencies:
- Scopes should be managed by business logic, not the DI container:
- Children has to know their parent (for dependency resolution).

**Conclusion:** The constructor-based approach `DIBox(parent=...)` is simpler and sufficient and avoids cyclic dependencies. Parent-managed lifecycles solve problems that rarely exist in practice.

Links
- [Dishka Scopes](https://dishka.readthedocs.io/en/latest/advanced/scopes.html)