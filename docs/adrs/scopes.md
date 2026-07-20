# Scopes

## Problem

Dependencies have different lifetimes. A database connection pool lives for the entire application; a per-request transaction context lives for one HTTP request; a user session cache sits somewhere in between. Without scope support, all instances share one flat container and one lifetime - the container's.

This means either:
- The developer manually creates and tears down short-lived containers in middleware, losing the benefits of DI for those objects.
- Or everything becomes effectively a singleton, which is incorrect for stateful, context-bound dependencies.

A scope mechanism should let the framework manage these lifetimes correctly, while keeping the developer's code focused on business logic rather than container plumbing.

## Key problems to solve
- how do we define what a "scope" is?
- how do we define to what instance box a dependency belongs to? (Note: currently each DIBox has one instance box, but we can move away from this 1-1 relationship)
- Can we define the same dependency in multiple scopes?
- how do we solve the problem of inter-dependencies with different scopes?
- what is the scope entry and exit points? How do we define them? What exactly happens on entry and exit?

## Container nesting

Container nesting is the foundational primitive for scopes. A child container inherits bindings and resolved instances from its parent, but owns its own short-lived instances independently.

```python
app_box = DIBox()
app_box.bind(AppConfig, load_config)
app_box.bind(DatabasePool, create_pool)

# Per-request: child inherits app-level bindings, adds request-specific ones.
async with DIBox(parent=app_box) as request_box:
    request_box.bind(RequestContext, RequestContext(request_id=request.id))

    ctx = await request_box.provide(RequestContext)   # owned by request_box
    pool = await request_box.provide(DatabasePool)    # resolved from app_box
    config = await request_box.provide(AppConfig)     # resolved from app_box
# request_box closes here - RequestContext is torn down, app-level instances are untouched.
```
### Binding modules inside scopes

Binding modules compose naturally with the container-nesting proposal. A `BindingBox`
defines what can be resolved inside a scope; the nested `DIBox` defines when that scope
starts and ends. These concerns should stay separate.

```python
# pipeline/gpu_stage.py — reusable recipe for any GPU-accelerated stage
gpu_stage_bindings = BindingBox()
gpu_stage_bindings.bind(GPUContext)
gpu_stage_bindings.bind(StageBuffer)

enhance_bindings = BindingBox()
enhance_bindings.bind(Enhancer)
```

```python
async with DIBox(parent=run_box) as stage_box:
    stage_box.add_bindings(gpu_stage_bindings)
    stage_box.add_bindings(enhance_bindings)
    stage_box.bind(StageContext, instance=StageContext("enhance", tmp_dir))
    enhancer = await stage_box.provide(Enhancer)
```

The module is reusable binding configuration. It does not own the lifetime boundary and
does not need to know whether it is added to an app, request, job, or pipeline-stage
container.

Note: We currently have an internal concept of "instance box" which is where resolved instances live. In the nesting design, we can either keep this 1-1 relationship (each container has one instance box) or allow multiple instance boxes per container (e.g. one per scope). Alternatively to the example above, parent and child relationship can be implemented between instance boxes instead of diboxes; the latter would manage the bindings and the scopes. We need to explore this further.

### Resolution rules

Child asks itself first, then delegates to parent. Once an instance is created, it lives in the container that created it.

### Shadowing semantics

A child can shadow a parent binding without affecting the parent or sibling containers.
This is useful for scope-specific configuration, such as tenant or request context. It
should not be the default testing strategy: tests should compose isolated test modules
with no fallback to non-test services.

```python
app_box.bind(CachePolicy, instance=CachePolicy(ttl=300))

async with DIBox(parent=app_box) as request_box:
    request_box.bind(CachePolicy, instance=CachePolicy(ttl=0))
    policy = await request_box.provide(CachePolicy)   # request-specific policy
    # app_box still resolves the app-level policy
```

### Instance ownership

Open question: if the parent has a binding for `DatabasePool` but hasn't created an instance yet, and a child requests it - who owns the instance?

Suggested rule: the container that holds the binding owns the instance. If the binding lives in the parent, the instance is created in and owned by the parent, even if the first `provide()` call happens through a child. Auto-wired types with no explicit binding are owned by the container that triggered the resolution. This ensures the instance outlives the child, which is the expected behavior for app-level dependencies.

Alternatively, stronger isolation can be implemented - only already existing instances are shared, and if a child triggers creation of a parent binding, the child owns it.

### Implicit creation and placement (brainstorm notes, unresolved)

Implicitly created instances make the ownership question sharper, and it is not solved yet. These notes record the framing, the constraint any answer must satisfy, and the candidate rules — as food for future thought, not a decision. See the [missing-binding policy](./missing_binding_policy.md) for the authorization side of the same discussion.

An explicit binding communicates three facts: how to construct an instance, that DIBox is intended to manage it, and which container lifetime owns it ("where you bind determines the scope"). Implicit self-binding gets the construction recipe from the class constructor. The missing-binding policy only authorizes DIBox to use that inferred recipe; it does not choose which container owns the resulting instance. Placement therefore needs a separate rule. This distinction is invisible with one flat container, but nesting makes it unavoidable: should an implicitly created instance live for the app, run, or stage?

**Lifetime invariant.** Any placement rule must satisfy: *an instance's dependencies must live in the same container or an ancestor* — a dependency must never be torn down before its dependent. The messed-up-graph caveat below (parent-bound ServiceC depending on child-shadowed ServiceB) is precisely a violation of this invariant, which is why it will be hard to debug. For explicit bindings placement is declared, so a future `validate()` can check the invariant statically over the bound subgraph; only implicit creations have inferred placement.

**Candidate placement rules, none locked:**

- *Requester owns* (the suggested rule above, applied to auto-wired types): simple, but violates the invariant upward. If a child triggers resolution of parent-bound `S`, and `S` pulls in unbound concrete `T`, placing `T` in the child means the child's exit calls `T.close()` while parent-owned `S` still holds it. Implicit dependencies of a parent-owned service must float to the parent.
- *Float to the binding owner's container*: fixes the case above, but reintroduces order dependence — the same unbound `T` pulled once by parent-bound `S` and once by child-bound `C` has two candidate homes, and whether one or two instances exist, and where, depends on which resolution ran first.
- *Container-local, never delegated* (current lean): implicit instances are private to the container whose resolution needed them; only explicit bindings participate in parent lookup. Deterministic and teachable in one sentence: "didn't bind it? it lives and dies with the container that needed it." Cross-scope sharing always requires a bind, because sharing *is* placement and placement is what binding declares. The parent-owned-service case is handled by evaluating implicit dependencies in the binding owner's container (forced by the invariant anyway). Cost: an expensive unbound type used in sibling scopes is silently re-created per scope — a perf/identity footgun until a `validate()` warning flags "type implicitly created in N sibling scopes; bind it where it belongs."

Supporting evidence for the conservative lean: in every scoped scenario in [scopes_sketch.py](./scopes_sketch.py) — stages, tenants, jobs, CLI commands, Ray workers — the scoped containers bind everything they own explicitly. Implicit creation earns its keep in the flat/app case and for transitive internals within one container; nothing in the scenarios relies on implicit creation across a scope boundary.

**Policy locality and inheritance.** A container's missing-binding policy should govern exactly the instances that will live in that container — an "open" child must not be able to place implicitly created instances into a "closed" parent. Open question: does `DIBox(parent=...)` inherit the parent's policy by default? Lean: inherit, overridable per child — a nested stage container is expected to behave like the app around it, and since scoped containers tend to bind explicitly anyway, inheritance is also safe.


### Lifecycle

Each container manages only its own instances. Children reference parents for resolution but don't create bidirectional ownership - no cyclic dependencies.

If a child outlives its parent, that is a usage error. The framework does not enforce this at runtime (no parent->child tracking), which keeps the implementation simple and avoids hidden coupling.

`DIBox(parent=...)` is the preferred API over `parent.create_child()`. The constructor-based approach keeps lifecycle management in the hands of business logic (middleware, context managers) rather than burying it inside the DI container.

### Possible implementation caveats
- Messed up dependency graphs. For example, ServiceA and ServiceB are bound to a child container, but ServiceA depends on ServiceC which depends on ServiceB. If ServiceC is only bound in the parent, this creates a situation where the parent will have its own ServiceB, not a shadowed version. It is unclear how to deal with this, but it will definitely hard to debug. Ideally we should issue a warning, because this can be missing shadowing of a parent binding.

## Connecting scoped containers to entry points

Container nesting gives us the primitive. The remaining question is: how do entry points (route handlers, task functions) get the right container?

### Manual scope management

The most transparent approach. Middleware creates a child container and passes it explicitly:

```python
app_box = DIBox()
app_box.bind(AppConfig, load_config)
app_box.bind(DatabasePool, create_pool)

@app.middleware("http")
async def di_middleware(request: Request, call_next):
    async with DIBox(parent=app_box) as request_box:
        request_box.bind(RequestContext, RequestContext(request_id=request.headers["X-Request-ID"]))
        request.state.container = request_box
        response = await call_next(request)
    return response

@app.get("/orders")
async def list_orders(request: Request):
    container = request.state.container
    service = await container.provide(OrderService)
    return await service.list_orders()
```

This works and is easy to debug. The cost is that every handler must fish out the container manually - no DI for the handler's own arguments. (Note: the 'fishing out' is solved with contextvars idea and `@inject`. This proposal is not fully ready yet.)

### Resolver-based scoping (Injector level)

The `resolver` setting on `Injector` (see `injection_modes.md`) eliminates this per-handler boilerplate by selecting the container at call time:

```python
app_box = DIBox()
app_box.bind(AppConfig, load_config)
app_box.bind(DatabasePool, create_pool)

api = Injector(resolver=lambda request: request.state.container)

@app.get("/orders")
@api.inject
async def list_orders(request: Request, service: Injected[OrderService]):
    return await service.list_orders()
```
The resolver cleanly connects the container to the injector, but
we still need middleware to manage its lifecycle:
```
# Middleware still creates the child container
@app.middleware("http")
async def di_middleware(request: Request, call_next):
    async with DIBox(parent=app_box) as request_box:
        request_box.bind(RequestContext, RequestContext(request_id=request.headers["X-Request-ID"]))
        request.state.container = request_box
        response = await call_next(request)
    return response
```

The middleware manages the container lifecycle; the resolver tells the injector where to find it.
The contextvars idea mentioned before is basically a convenience layer on top of this pattern, where the resolver is implicitly `lambda: global_dibox.get()` and the middleware sets the a context var instead of request state.

#### Yield vs. return: lifecycle ownership in the resolver

An interesting extension from the original design notes: what if the resolver itself could manage the container lifecycle?

- **Return:** resolver borrows an existing container. Lifecycle is managed elsewhere (middleware, session store). This is the common case.
- **Yield:** resolver creates and yields a new container. The injector wraps the call in a context manager and tears down the container after the function returns.

```python
async def fresh_container(request: Request) -> AsyncIterator[DIBox]:
    async with DIBox(parent=app_box) as box:
        box.bind(RequestContext, RequestContext(request_id=request.headers["X-Request-ID"]))
        yield box

per_request_api = Injector(resolver=fresh_container)
```

The yield variant makes the middleware unnecessary for simple transient containers.

**Tradeoff:** yield-based resolvers are convenient for quick setups but may confuse users about who owns the container. For production apps with structured middleware, the return-based resolver is likely the better default. The yield variant could be supported but should be documented as an advanced pattern.

### Resolver stack (Injector level)
Instead of a single resolver, we could introduce 'middleware' resolver for the injector itself, so we have a stack of resolvers instead of just one. In case if a wrapped function does not contain the required context for resolution, the next resolver in the stack will be used.

```python
app_injector = Injector(container=app_box) # pass a default container

# decorator is just one way to add resolvers to the stack, we can also have an API like `app_injector.add_resolver(...)`
@app_injector.resolver
async def request_scope(request: Request) -> AsyncIterator[DIBox] | None:
    # this resolver only handles requests
    async with DIBox(parent=app_box) as request_box:
        request_box.bind(RequestContext, RequestContext(request_id=request.headers["X-Request-ID"]))
        yield request_box

@app_injector.inject
def list_orders(request: Request, service: Injected[OrderService]):
    # will have request scope
    return await service.list_orders()

@app_injector.inject
def health_check():
    # will have app scope
    return await health_service.snapshot()
```

The resolver idea only solves the problem of connecting entry points to the right container. It doesn't solve the problem of defining scopes and their boundaries!

### Explicit scope declarations (Guice/Dishka style)

```python
app_box = DIBox()
app_box.bind(AppConfig, scope=AppScope)
app_box.bind(OrderService, scope=RequestScope)
app_box.bind(NotificationClient, scope=TransientScope)
```

- App, request, transient are the common scopes, but users must be able to define custom scopes.
- How are scope boundaries defined? The container needs to know when a "request" starts and ends. This either requires middleware integration or explicit `enter_scope()` / `exit_scope()` calls.
- **How does it interact with container nesting?** If nesting already provides scope boundaries via `async with`, adding a parallel scope system risks redundancy or conflict.
- How the scopes themselves are nested? Is it a simple hierarchy (app > request > transient) or can they be orthogonal?

```
# all suggested API is just a sketch! For example, enter_scope can be
# implemented in many ways, it can be a free function, or implicitly called
# by constructor of a child container (`DIBox(scope=..., parent=...)`), etc.

# somewhere in middleware
with app_box.enter_scope(RequestScope) as request_container:  # this would create a new instance box or dibox
    # ehm. okay what do we do here?
    request_container.resolve(OrderService)  # creates a request-scoped instance in the request container

#somewhere in an app definition
@inject
def handler(service: Injected[OrderService]):
    # how do we get the right container here? Get it through a context variable that tracks the current scope?
    service = request_container.resolve(OrderService)  # how do we get request_container here?
```

Note: we are strict typed library, so scopes should be real types that typecheckers can check.

## Afterthoughts
After writing few scenarios as a sketch, it is clear that container nesting is the core primitive for scopes. It gives us explicit boundaries and instance ownership — `async with DIBox(parent=...)` is both the scope boundary and the lifecycle manager. Adding a parallel named-scope system with `scope=` parameter for `bind(...)` creates two ways to express the same thing and raises questions nobody has good answers to (who manages scope lifecycle? how do named scopes nest?). Container nesting already answers these structurally.

## Priority ranking (as a user building real things)

1. `DIBox(parent=...)` — the foundation. Without nesting, nothing else matters. This gives scope boundaries and instance isolation with zero new concepts.

2. `container.call(func, **explicit_args)` — the biggest DX win for pipeline/orchestration code. Greedy resolution eliminates chains of `provide()` calls and doesn't require @inject on internal helpers.

3. Contextvar-based `@inject` — evolves `global_dibox` from a singleton into a scope-aware contextvar stack. Entering `async with DIBox(parent=...)` sets the "current" container; `@inject` resolves from it. This is the bridge for framework entry points (routes, CLI commands, task handlers).


## What to skip for now

- `scope=` on `bind()` — redundant with nesting. Creates a second conceptual axis.
- Named scope enums (`RequestScope`, `SessionScope`) — framework-specific vocabulary, not the primitives a generic library should provide.
- Resolver stack / middleware chain — premature. A single resolver (or contextvar default) covers 95% of real cases.

The key insight from the pipeline examples: scopes aren't about "request" vs "session" — they're about **ownership boundaries for resources that must be created and torn down together**. GPU contexts, temp directories, tenant DB connections, job trackers. Container nesting makes these boundaries explicit in the code structure itself, which is both simpler and more debuggable than declarative scope annotations.

## Links

- [Dishka Scopes](https://dishka.readthedocs.io/en/latest/advanced/scopes.html)
- [Google Guice Scopes](https://github.com/google/guice/wiki/Scopes)
- [dependency-injector Wiring](https://python-dependency-injector.ets-labs.org/wiring.html)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [.NET Dependency Injection Lifetimes](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection#service-lifetimes)