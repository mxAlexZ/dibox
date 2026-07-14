
# bind(...) API

## Basic usage:
 Separate arguments for different binding types:
```python
box.bind(type)
box.bind(type, target)
box.bind(type, name, target)
box.bind(type, name, factory=...)
box.bind(type, name, instance=...)
box.bind(type, name, target=...)
```


`bind(T)` with a single type argument self-binds a concrete type — equivalent to `bind(T, T)`. This is
primarily useful in strict mode where implicit self-binding is disabled and every managed type must
be registered explicitly, without the noise of repeating the name twice:

```python
box.bind(ServiceA)
box.bind_many(ServiceA, ServiceB, ServiceC)
box.bind_many(
    (PortA, PortAImpl),
    (Client, "primary", PrimaryClient)
)
```

`bind_many(*items)` is a thin wrapper that forwards each item to `bind(...)` using the same
positional forms (`T`, `(T, target)`, `(T, arg_name, target)`, `(predicate, target)`).
No new binding model —
resolution, precedence, and override behavior are unchanged.

## Yield and context managers

### Motivation

Some resources are naturally expressed as generators or context managers — especially third-party clients
that already ship as context managers (database sessions, HTTP clients, file handles). Forcing users to
split setup and teardown into separate methods, or wrap external code, is exactly the kind of boilerplate
DIBox is meant to avoid.

Two patterns are in scope:

```python
# 1. Plain generator function
def create_db_session(engine: Engine):
    session = engine.connect()
    yield session
    session.close()

# 2. Async generator function
async def create_http_client(settings: Settings):
    async with httpx.AsyncClient(base_url=settings.api_url) as client:
        yield client

# 3. @contextmanager / @asynccontextmanager decorated function (already a context manager factory)
@contextmanager
def create_service(dep: SomeDep):
    service = Service(dep)
    try:
        yield service
    finally:
        service.cleanup()
```

All three patterns share the same intent: setup before yield, instance is the yielded value,
teardown is post-yield code. From the user's perspective, binding them should feel identical
to binding an ordinary factory:

```python
box.bind(Session, create_db_session)
box.bind(httpx.AsyncClient, create_http_client)
box.bind(Service, create_service)
```

### DX analysis

**Strengths:**
- Setup and teardown stay co-located — much easier to read than a class with `start()`/`close()`.
- Zero changes required to existing generator-based code. If a user already has a `@contextmanager`
  helper, they can register it directly.
- Maps naturally to FastAPI's `yield`-based `Depends`, so the pattern is familiar to a large audience.
- Works cleanly for third-party resources (`httpx.AsyncClient`, SQLAlchemy sessions, `boto3` clients)
  without any wrapper classes.

## Rejected ideas
- Fluent API style:
  `box.for_type(type).to(factory).named('orders').with_kwargs(a=..., b=...)`

- Explicit factory binding method:
    `box.bind_factory(type, factory_func, name="_name_")`
    `box.bind_instance(type, instance, name="_name_")`
    `box.bind_implementation(type, implementation, name="_name_")`
