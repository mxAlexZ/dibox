# Implicit Self-Binding

Status: implemented

Related decisions:
- [Missing-Binding Policy](./missing_binding_policy.md): decides when this mechanism may be used after binding lookup fails.
- [Dependency Graphs](./dependency_graph.md): owns binding lookup, constructor inspection, recursive graph compilation, and caching.
- [Scopes](./scopes.md): owns the unresolved placement of implicitly created instances across nested containers.

## Problem

Concrete service constructors often contain the complete recipe for building their objects. If `UserService` requires `UserRepo` and `Logger`, registering self-bindings for all three classes repeats the dependency structure already expressed by their annotations. It also forces the composition root to know and import graph internals even when it has no implementation, configuration, or lifetime decision to make.

DIBox needs a construction mechanism that can use those existing recipes without first materializing them as explicit registrations.

## Decision

When no explicit binding matches and the missing-binding policy authorizes implicit creation, DIBox treats the requested concrete class as its own factory. This generated binding is an implicit self-binding.

The class constructor is inspected like any other factory:

- Required annotated parameters become dependency requests and are resolved recursively.
- Optional parameters keep their constructor defaults.
- Variadic parameters are ignored.
- The resulting instance is cached and lifecycle-managed like one produced by an explicit binding.

Explicit bindings always win over generated self-bindings.

## Limits of constructor-derived bindings

An implicit self-binding can express only what DIBox can derive from the requested class itself. It cannot select an implementation for an abstract request, supply configured values, distinguish named variants, or resolve a required parameter without an annotation. Those cases contain intent absent from the constructor and require an explicit binding.

Constructor annotations must evaluate to runtime dependency types. Unsupported annotations and classes whose signatures cannot be inspected fail during graph construction with resolution context.

Class style and constructor shape do not change the mechanism. Plain classes, dataclasses, attrs classes, and zero-dependency classes all self-bind in the same way when eligible.
