# Greedy resolution and `container.call()`

## Background

DIBox has two resolution modes in practice:

- **Structural auto-wiring** (`provide(SomeService)`) — the container inspects
  `SomeService.__init__`, recursively resolves each dependency, and constructsthe
  full object graph. Explicit bindings are used where available; unbound types are
  constructed directly if their own dependencies can be resolved.
- **Greedy resolution** (`call(func, **explicit_args)`) — proposed for
  `container.call()`: the container inspects `func`'s signature, fills every typed
  parameter it *can* resolve, and leaves the rest as caller-supplied arguments.

The zero-configuration convenience of auto-wiring (bind `DatabaseConfig`, get every
service that needs it for free) is one of core DIBox selling points. Greedy `call()` extends
that convenience to arbitrary functions — useful for pipeline orchestration, CLI entry
points, and Ray workers — without requiring `Injected[]` markers.

## The problem: overly helpful construction

Both modes share one failure mode. Because auto-wiring recurses into unbound types,
a misconfigured graph silently materialises the wrong objects:

```python
class AppConfig:
    def __init__(self, storage_url: str, model_registry_url: str) -> None: ...

class StorageClient:
    def __init__(self, config: AppConfig) -> None: ...

box = DIBox()
# Forgot to bind AppConfig. Container still "succeeds":
# StorageClient <- AppConfig <- str(""), str("")
client = await box.provide(StorageClient)  # no error, wrong data
```

The same problem amplifies for `call()`: a function with many parameters becomes a
landmine where any typed parameter that maps to a zero-arg-constructable type gets
silently filled with a meaningless default.

## Problem taxonomy

Two distinct issues:

1. **Value type construction** — `str`, `int`, `Path`, `list`, `datetime`, and
   similar types are constructable with zero arguments. The result is semantically
   empty, rarely useful as a dependency, never the developer's intent.

2. **Zero-dep user service** — a user-defined class with no dependencies, e.g.
   `InMemoryCache()`. Zero-arg construction is valid, so the current rules don't
   distinguish it from a value type. Whether this should be auto-wired is more
   contextual (see Options below).

## Proposed rule: blacklist zero-required-params types

Don't auto-construct any type where `inspect.signature` shows no required parameters
(all params have defaults or there are none).

```python
def _is_autowireable(t: type) -> bool:
    try:
        sig = inspect.signature(t)
    except (ValueError, TypeError):
        return False  # C extensions, special forms — treat as blacklisted
    return any(
        p.default is inspect.Parameter.empty
        and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for p in sig.parameters.values()
    )
```

The check runs on the type being resolved, not on a hardcoded list. This covers the
entire stdlib, all value types, and builtins without maintaining an explicit blacklist.

### What this correctly rejects

| Type | Call | Outcome |
|---|---|---|
| `str` | `str()` | 0 required params → reject |
| `Path` | `Path()` | 0 required params → reject |
| `list`, `dict`, `set` | `list()` | 0 required params → reject |
| `datetime` | requires args? no, `datetime.now()` is classmethod; bare `datetime()` would fail | 0 required → reject |
| `RateLimiter(rps=100, burst=200)` | `RateLimiter()` succeeds | 0 required params → reject |
| `InMemoryCache()` | `InMemoryCache()` succeeds | 0 required params → reject |

### What this still allows

| Type | Required params | Outcome |
|---|---|---|
| `AppConfig(storage_url: str, ...)` | yes | allowed (but `str` resolution will fail) |
| `StorageClient(config: AppConfig)` | yes | allowed |

### Caveats

**Zero-dep user service classes** (`InMemoryCache`, `EventBus`): the rule rejects
auto-wiring for these, requiring `box.bind(InMemoryCache)`. One extra line —
but if there are no dependencies to wire, the container adds no real value for
construction anyway. This is a mild forcing function for being intentional.

**All-defaults services** (`RateLimiter(rps=100, burst=200)`): also rejected by the
rule. The user may want the defaults used as production config. Requires explicit
`box.bind(RateLimiter)`. This is reasonable: "use the defaults for this service" is
a binding decision that should be stated once.

**Signature inspection failures**: C extension types, some `__new__`-based types,
parameterised generics (`list[str]`). These should fall back to blacklisted (the
conservative choice) with the same error as a regular value type.

**Error locality**: the rule raises an error at the *leaf* (`str`), not at the point
where the misconfiguration actually lives (`AppConfig`). See Resolution stack below.

## `call()` and greedy resolution semantics

`call(func, user_id=42)` has a different contract from `provide(SomeService)`:
- `provide` → "construct this type completely, resolving its full dependency graph"
- `call` → "run this function; fill what you know about, leave the rest for the caller"

The second contract calls for **bound-only resolution**: `call()` only injects
parameters where the container has an explicit binding. Unbound parameters are left
unset — they become required caller arguments.

This is a stronger rule than the zero-dep guard:

```python
async def process(user_id: int, db: Database, config: AppConfig) -> Result:
    ...

# box has Database bound, AppConfig bound, no int binding
await box.call(process, user_id=42)
# -> db and config injected, user_id passed by caller. int never attempted.
```

The combination:
- `provide` uses structural auto-wiring + zero-dep guard
- `call` uses bound-only resolution (zero-dep guard is then a bonus safeguard, not
  the primary mechanism)

## Resolution stack for meaningful error messages

Currently, resolution errors report the immediate failing type. For value type errors
this is always a leaf node (`str`, `int`, `Path`), which tells the developer nothing
useful about where the problem actually is.

Useful error:
```
Cannot resolve StorageClient:
  dependency AppConfig cannot be auto-wired (no explicit binding found)
  dependency str is a value type and will never be auto-constructed
  → did you forget to bind AppConfig?
```

This requires tracking the resolution stack — a list of types currently being resolved,
updated as `_create_instance` recurses. The stack is already implicitly present in the
call frames; it just needs to be made explicit (e.g. a `list[type]` threaded through
`_provide_dependencies` and `_create_instance`).

The stack also unlocks cycle detection: if a type appears twice in the current chain,
the container is in a circular dependency and can raise immediately with the full chain
shown.

## Summary

| Problem | Fix |
|---|---|
| Value types silently constructed | Zero-required-params guard in `provide()` |
| `call()` resolves too aggressively | Bound-only semantics for `call()` |
| Error messages point at the wrong layer | Resolution stack tracking |
| Circular dependencies silently hang | Cycle detection from the same stack |

The zero-dep guard and bound-only `call()` are independent changes; neither depends on
the resolution stack, which can be added later as a debuggability improvement.
