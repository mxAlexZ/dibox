# Implicit Creation Policy

Status: implemented. The policy, its built-in guards, and dependency-graph integration exist; denials raise resolution errors that name the deny rule or guard and include the resolution path.

Related documents:
- [Implicit Self-Binding](./implicit_self_binding.md): defines the implicit self-binding mechanism and the resolution-mode boundaries where this policy can apply.
- [Zero-Dependency Guard](./zero_dependency_guard.md): earlier leaf-node safety proposal this policy generalizes.
- [Semi-Strict Resolution](./semi_strict_mode.md): uses explicit roots with implicit transitive expansion, where this policy is most useful.
- [Strict Mode](./strict_mode.md): disables implicit self-binding entirely, so this policy has no construction work to approve.
- [Diagnostics and Introspection](./diagnostics.md): should report policy decisions during resolution and future validation.

## 1. Problem

Implicit self-binding removes registration noise for concrete graph internals, but deciding which unbound concrete types may be created cannot rest on constructor shape alone. A guard that rejects any concrete class with no required constructor parameters catches real bugs: values, secrets, configuration objects, defaulted policy objects, and external resources should not appear in the graph just because the container can call `Type()`.

The same shape-based rule also rejects legitimate application-owned leaves. UI and view layers often contain many concrete zero-dependency classes. They construct their own child elements, do not need configuration, and are still valid graph internals. Requiring every such leaf to be imported and bound at the composition root turns a safety guard into boilerplate and leaks internal structure across package boundaries.

The safety question is not whether a constructor has required parameters. The safety question is whether DIBox is allowed to implicitly create this unbound concrete type in this application.

## 2. Decision

DIBox governs implicit creation with an explicit policy rather than a fixed constructor-shape guard.

Resolution mode still decides where implicit self-binding may happen:

- Permissive mode may apply it to requested roots and transitive dependencies.
- Semi-strict mode may apply it only to transitive dependencies below explicit roots.
- Strict mode disables implicit self-binding, so the policy is not consulted for missing bindings.

The implicit creation policy decides whether a specific missing concrete type may be self-bound at a point where the resolution mode permits implicit self-binding.

Explicit bindings bypass this policy. A binding is already a declaration that the container owns construction for that selector.

## 3. Policy model

The policy is a small allow/deny rule set, not an ordered packet-filter chain.

Rules evaluate with these semantics:

- Requests that are not runtime classes, such as parameterized generic aliases and unions, are rejected before configurable rules run.
- Deny rules override allow rules.
- Allow rules are additive: any matching allow rule is enough unless a deny rule also matches.
- If no deny rule and no allow rule match, the selected built-in guard decides.

This keeps the common case simple:

```python
implicit = ImplicitCreationPolicy()
implicit.allow_package("my_app")
implicit.deny_package("my_app.config")
```

`my_app.views.ButtonPanel` is allowed by package ownership. `my_app.config.AppConfig` is denied even though it is inside `my_app`, because explicit deny rules are stronger than broad ownership allows. Types that match neither rule use the selected guard.

Package rules include subpackages by default. Matching is package-boundary matching, not raw string prefix matching:

```python
module == package or module.startswith(package + ".")
```

## 4. Guards and rule vocabulary

`ImplicitCreationPolicy` defaults to `guard="value-types"`. Its guard choices are:

- `"none"`: permit unruled concrete types.
- `"value-types"`: deny exact requests for `str`, `int`, `float`, `bool`, `bytes`, `list`, `dict`, `set`, `tuple`, `Path`, `Decimal`, and `UUID`; permit other unruled concrete types.
- `"zero-dependency"`: deny unruled concrete types whose constructor has no required parameters.
- `"deny-all"`: deny every unruled concrete type, making allow rules a strict allowlist.

`"value-types"` serves two distinct purposes: for introspectable types like `Path` and `list`, it prevents silent injection of meaningless default values (`Path('.')`, `[]`); for C builtins like `str`, `int`, and `bytes` whose introspectability varies across Python versions, it provides a consistent semantic error. These concerns are separate: signature introspection failure is handled at the dependency graph level regardless of which guard is in use. `"zero-dependency"` provides the conservative constructor-shape behavior for applications that want it. `"deny-all"` closes implicit creation to types not approved by allow rules. Strict resolution remains separate: it disables implicit self-binding entirely, while a deny-all policy still permits matching allow rules wherever the resolution mode permits implicit creation.

The primary API covers package ownership and custom predicates.

Package rules are the main ergonomic feature:

```python
implicit.allow_package("my_app")
implicit.deny_package("my_app.config")
implicit.deny_package("my_app.resources")
```

All rule methods accept an optional keyword-only `name` used in diagnostics:

```python
implicit.deny_if(is_deprecated_type, name="deprecated integration")
```

Type rules match exact requested type hints. DIBox does not infer hierarchy intent; users can express it explicitly with a predicate rule. `ImplicitCreationRule`, `allow_rules`, and `deny_rules` are public for projects that need direct rule construction beyond the convenience methods.

Predicate rules are the escape hatch for uncommon or project-specific logic:

```python
def is_view_type(cls: type[object]) -> bool:
    return cls.__name__.endswith("View")

implicit.allow_if(is_view_type)
implicit.deny_if(lambda cls: cls.__module__.startswith("legacy."))
```

Package names cover the expected common case, and predicates let users express arbitrary matching when they really need it.

## 5. Zero-dependency guard as an optional guard

The zero-dependency guard is available but is not the default and not the whole decision. Select it explicitly when an application wants conservative treatment of unruled leaves:

```python
implicit = ImplicitCreationPolicy(guard="zero-dependency")
```

Its purpose is to block accidental implicit construction of suspicious leaves:

- introspectable zero-dep types where zero-arg construction is meaningless as a dependency: `Path()` gives `Path('.')`, `list()` gives `[]`,
- configuration and secrets where defaults may hide missing setup,
- external clients, pools, and resources that need lifecycle or environment choices,
- all-default policy objects where defaults are real application decisions.

C builtins (`str`, `int`, `bool`, `bytes`, etc.) are listed for completeness but are typically non-introspectable on CPython — they would fail at signature inspection regardless of this guard. The guard provides a consistent semantic error for them across Python versions where introspection behavior varies.

An explicit allow rule overrides the guard, while an explicit deny rule remains stronger than every allow. A failure says that implicit creation was denied by a rule or guard, not merely that the constructor has no required parameters.

An explicit binding still bypasses the guard:

```python
box.bind(RateLimiter)
```

That line declares that default construction is intentional container-owned behavior.

## 6. Construction style is not semantic category

DIBox should not classify services and data objects by whether they use vanilla classes, dataclasses, attrs, Pydantic, or another declarative constructor style.

Those tools can describe data transfer objects, configuration, services, views, widgets, commands, or policy objects. Declarative class styles are often used because they document attributes well and make component APIs visually clear.

Package ownership and explicit policy rules are a better signal than decorator choice. Projects that want to deny dataclasses or attrs classes can do so with a predicate rule; DIBox should not make that a default semantic assumption.

## 7. Diagnostics and mutation

A denied implicit creation raises a resolution error that reports the requested type, the resolution path, and whether the decision came from a specific deny rule or from the built-in guard. Rule names, including the optional `name=` label, appear in that reason text.

One interaction is not yet reported: when a deny rule overrides a matching allow rule, the error names only the deny rule. Deny rules are evaluated first and returned immediately, so the overridden allow is not surfaced. This matters because package ownership rules are intentionally broad; when a type under `my_app` is denied by `my_app.config`, showing the overridden allow would explain the interaction instead of leaving the user to infer it. Policy decisions are likewise not yet surfaced in validation or graph output, which do not exist yet.

The policy is exposed as `box.implicit_creation_policy` and its rule lists are mutable. Changes apply to subsequent policy evaluations; dependency-graph nodes already cached by the container remain unchanged. Configure policy before resolution for deterministic application setup.

## 8. Trade-offs

Benefits:

- Keeps the original safety goal: avoid accidental construction of values, configuration, resources, and meaningful defaults.
- Removes composition-root import pressure for legitimate zero-dependency application internals.
- Gives users a small, understandable ownership boundary: usually `allow_package("my_app")` plus a few denies.
- Keeps advanced matching possible without committing DIBox to a large pattern language.

Costs and limits:

- A broad package allow can still permit accidental construction inside that package. Deny rules and validation diagnostics mitigate this but do not make implicit creation a correctness proof.
- Deny-overrides-allow makes carve-outs inside denied packages awkward. Predicate rules can handle rare cases; a dedicated exception mechanism can be added later if real usage demands it.
- Required-parameter constructors can still be implicitly self-bound incorrectly. This policy addresses ownership and suspicious leaves, not interface selection or every possible graph mistake.

## 9. Allowlist mode

The `"deny-all"` guard makes allow rules a strict whitelist without changing rule precedence:

```python
implicit = ImplicitCreationPolicy(guard="deny-all")
implicit.allow_package("my_app.services")
implicit.deny_package("my_app.services.legacy")
```

Only matching allowed types may be created implicitly, and deny rules still override broad allows. A catch-all deny rule cannot provide these semantics because deny-overrides-allow would also reject every allowed type. This guard is useful when an application wants a closed ownership boundary while retaining implicit wiring inside selected packages. It is intentionally distinct from strict resolution, which does not consult allow rules because it disables implicit self-binding.

## 10. Implementation notes

The dependency graph asks the policy whether it may self-bind an unbound concrete type only after resolution mode permits implicit binding and binding lookup fails. Explicit bindings, including explicit self-bindings, bypass the policy.