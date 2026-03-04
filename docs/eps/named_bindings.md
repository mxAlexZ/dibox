
# Named bindings
Current approach is to use argument name to resolve named bindings.
It works well in most cases but has limitations:
- It couples the function signature to the DI configuration. Renaming a parameter requires updating the binding name and IDE can't help with refactoring.
- No compile-time safety: Names are plain strings—typos like `name="usres"` vs `name="users"` won't be caught until runtime, potentially causing hard-to-debug resolution failures.
- Poor discoverability: Developers must grep through `bind()` calls to find available named bindings. There's no central registry or IDE autocompletion.

## Possible Solutions

### Solution 1: Unified Identifier-Based Injection

Unify "named" and "token" bindings by allowing any hashable object to serve as a binding identifier. Keep the simple `name` parameter in `bind`, but make it accept either a string or a type-safe token object.

The injector uses `typing.Annotated` metadata to match parameters to binding identifiers.
Both `Annotated[ContainerClient, Named("users")]` and `Annotated[ContainerClient, "users"]` should work, while `Named` is used to prevent potential ambiguity with other metadata.

```python
from typing import Annotated
from dibox import Named, Token

# 1) Bind with a simple string identifier
box.bind(ContainerClient, create_users_container, name="users")

class DataService:
    def __init__(
        self,
        # Explicitly mark the identifier to avoid metadata ambiguity
        user_storage: Annotated[ContainerClient, Named("users")]
    ):
        self.users = user_storage

# 2) Bind with a type-safe token identifier
USERS_CONTAINER = Token("A unique token for the users container")
box.bind(ContainerClient, create_users_container, name=USERS_CONTAINER)

class DataServiceWithToken:
    def __init__(
        self,
        user_storage: Annotated[ContainerClient, USERS_CONTAINER]
    ):
        self.users = user_storage
```

**Pros:**
- Unified and flexible: one mechanism covers simple strings and robust tokens.
- Explicit and unambiguous: `Named`/`Token` clearly signal DI metadata usage.
- Refactor-safe for tokens: IDE can rename and find usages reliably.
- Non-invasive: annotations are metadata; classes work without DI.
- Preserves convention-over-configuration: argument-name matching can remain the default, with `Annotated` as the explicit override.

**Cons:**
- More verbose than implicit argument-name matching.
- Requires modifying signatures—only applicable to code you control.

**Important Distinction: First-Party vs. Third-Party Code**

The `Annotated`-based approach is an *opt-in escape hatch* for code you own. For **third-party libraries** (e.g., Azure SDK clients), argument-name matching remains the only viable—and genuinely non-invasive—strategy.

Example: Auto-wiring Azure credentials into SDK clients:

```python
# Azure SDK client constructors expect a parameter named `credential`
# BlobServiceClient(account_url: str, credential: TokenCredential, ...)

# Bind by name to match the SDK's expected parameter name
box.bind(TokenCredential, DefaultAzureCredential(), name="credential")

# DIBox auto-wires `credential` into any class that expects it
blob_client = await box.provide(BlobServiceClient)
```

This works seamlessly because:
- You cannot (and should not need to) modify Azure SDK signatures.
- The parameter name `credential` is part of Azure's public API contract—unlikely to change without a major version bump.
- Runtime errors from name mismatches are inherent to any third-party integration; no DI pattern can fully eliminate this risk.

**Conclusion:** Argument-name matching is "good enough" and correct for third-party integration. Use `Annotated` when you control the code and want stronger guarantees.

### Solution 2: NewType-Based Differentiation
Leverage `typing.NewType` to create distinct types for each binding, avoiding named bindings entirely.

```python
from typing import NewType

UsersContainer = NewType('UsersContainer', ContainerClient)
OrdersContainer = NewType('OrdersContainer', ContainerClient)

box.bind(UsersContainer, create_users_container)
box.bind(OrdersContainer, create_orders_container)

class DataService:
    def __init__(self, users: UsersContainer, orders: OrdersContainer):
        ...
```

**Pros:**
- Uses standard library typing—no DIBox-specific markers.
- IDE support for autocompletion and "find usages."
- Type-safe at the DI level; each NewType is a distinct binding key.

**Cons:**
- `NewType` is a type alias, not a real type—runtime checks (`isinstance`) don't work.
- May confuse static type checkers in some edge cases.
- Requires creating a NewType for every named variant.

## Recommendation

Align with **convention-over-configuration** and **non-invasive design** via a unified, layered approach:
1. **Keep argument-name matching as the default** for simple cases—zero configuration, minimal friction.
2. **Adopt unified identifier-based injection**: support both `Annotated[T, Named("...")]` for string names and `Annotated[T, TOKEN]` for type-safe tokens; allow `bind(..., name=identifier)` where `identifier` is any hashable.

This preserves "easy things are easy" while making harder, large-scale scenarios robust and refactor-friendly.

Links:
- [Dishka components](https://dishka.readthedocs.io/en/latest/advanced/components.html)