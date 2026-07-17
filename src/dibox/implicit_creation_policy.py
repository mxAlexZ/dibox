from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Callable, Literal, TypeAlias
from uuid import UUID

TypePredicate: TypeAlias = Callable[[type[Any]], bool]
ImplicitCreationGuardValue: TypeAlias = Literal["none", "value-types", "zero-dependency", "deny-all"]
_VALUE_TYPES = (str, int, float, bool, bytes, list, dict, set, tuple, Path, Decimal, UUID)


class ImplicitCreationGuard(StrEnum):
    """Fallback behavior when no explicit implicit-creation rule matches."""

    NONE = "none"
    """
    Allow every unmatched concrete type. Explicit deny rules can still impose
    targeted restrictions.
    """

    VALUE_TYPES = "value-types"
    """
    Deny known exact value types, such as ``str`` and ``Path``.
    This default protects configuration and value injection while allowing
    ordinary zero-dependency application and view classes.
    """

    ZERO_DEPENDENCY = "zero-dependency"
    """
    Deny unmatched types with no required constructor
    parameters, including types whose signatures cannot be inspected.
    Use this more conservative fallback when zero-dependency leaves must
    be explicitly allowed by a rule.
    """

    DENY_ALL = "deny-all"
    """Deny every unmatched concrete type, making allow rules a strict allowlist."""


@dataclass(slots=True)
class ImplicitCreationDecision:
    allowed: bool
    reason: str


@dataclass(slots=True)
class ImplicitCreationRule:
    matches: TypePredicate
    name: str


class ImplicitCreationPolicy:
    """Controls which unbound concrete types DIBox may create implicitly."""

    __slots__ = ("allow_rules", "deny_rules", "guard", "_check_guard")

    def __init__(
        self,
        guard: ImplicitCreationGuard | ImplicitCreationGuardValue = ImplicitCreationGuard.VALUE_TYPES,
    ) -> None:
        self.allow_rules: list[ImplicitCreationRule] = []
        self.deny_rules: list[ImplicitCreationRule] = []
        self.guard = ImplicitCreationGuard(guard)
        match self.guard:
            case ImplicitCreationGuard.VALUE_TYPES:
                self._check_guard = _check_value_types_guard
            case ImplicitCreationGuard.ZERO_DEPENDENCY:
                self._check_guard = _check_zero_dependency_guard
            case ImplicitCreationGuard.DENY_ALL:
                self._check_guard = _check_deny_all_guard
            case _:
                self._check_guard = _check_none_guard

    def allow_package(self, *packages: str, name: str | None = None) -> None:
        """Allow types defined in packages and their subpackages."""
        self.allow_rules.append(_make_package_rule(packages, name))

    def deny_package(self, *packages: str, name: str | None = None) -> None:
        """Deny types defined in packages and their subpackages."""
        self.deny_rules.append(_make_package_rule(packages, name))

    def allow_if(self, predicate: TypePredicate, *, name: str | None = None) -> None:
        """Allow types matching predicate."""
        self.allow_rules.append(_make_predicate_rule(predicate, name))

    def deny_if(self, predicate: TypePredicate, *, name: str | None = None) -> None:
        """Deny types matching predicate."""
        self.deny_rules.append(_make_predicate_rule(predicate, name))

    def allow_type(self, *types: type[Any], name: str | None = None) -> None:
        """Allow exactly the supplied types."""
        self.allow_rules.append(_make_type_rule(types, name))

    def deny_type(self, *types: type[Any], name: str | None = None) -> None:
        """Deny exactly the supplied types."""
        self.deny_rules.append(_make_type_rule(types, name))

    def decide(self, requested_type: object) -> ImplicitCreationDecision:
        """Return whether requested_type may be created implicitly."""
        if not isinstance(requested_type, type):
            return ImplicitCreationDecision(False, "denied because request is not a concrete class")
        denied_by = _match_rules(self.deny_rules, requested_type)
        if denied_by is not None:
            return ImplicitCreationDecision(False, f'denied by rule "{denied_by.name}"')
        allowed_by = _match_rules(self.allow_rules, requested_type)
        if allowed_by is not None:
            return ImplicitCreationDecision(True, f'allowed by rule "{allowed_by.name}"')
        return self._check_guard(requested_type)


def _make_package_rule(packages: tuple[str, ...], name: str | None) -> ImplicitCreationRule:
    if not packages:
        raise ValueError("at least one package is required")
    if any(not package for package in packages):
        raise ValueError("package names must not be empty")
    rule_name = name or f"package {', '.join(packages)}"
    return ImplicitCreationRule(
        lambda req_type: any(
            req_type.__module__ == package or req_type.__module__.startswith(f"{package}.")
            for package in packages
        ),
        rule_name,
    )

def _make_predicate_rule(predicate: TypePredicate, name: str | None) -> ImplicitCreationRule:
    rule_name = name or getattr(predicate, "__name__", None) or str(predicate)
    return ImplicitCreationRule(predicate, rule_name)

def _make_type_rule(types: tuple[type[Any], ...], name: str | None) -> ImplicitCreationRule:
    if not types:
        raise ValueError("at least one type is required")
    rule_name = name or f"type {', '.join(t.__name__ for t in types)}"
    return ImplicitCreationRule(lambda req_type: any(req_type is t for t in types), rule_name)

def _match_rules(rules: list[ImplicitCreationRule], requested_type: type[Any]) -> ImplicitCreationRule | None:
    return next((rule for rule in rules if rule.matches(requested_type)), None)

def _check_value_types_guard(requested_type: type[Any]) -> ImplicitCreationDecision:
    if requested_type in _VALUE_TYPES:
        return ImplicitCreationDecision(False, "denied by value-types guard")
    return ImplicitCreationDecision(True, "allowed by value-types guard")

def _check_zero_dependency_guard(requested_type: type[Any]) -> ImplicitCreationDecision:
    try:
        type_signature = signature(requested_type, eval_str=True)
    except (TypeError, ValueError):
        return ImplicitCreationDecision(False, "denied by zero-dependency guard")
    has_required_parameter = any(
        parameter.default == Parameter.empty
        and parameter.kind not in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD)
        for parameter in type_signature.parameters.values()
    )
    if not has_required_parameter:
        return ImplicitCreationDecision(False, "denied by zero-dependency guard")
    return ImplicitCreationDecision(True, "allowed by zero-dependency guard")

def _check_deny_all_guard(requested_type: type[Any]) -> ImplicitCreationDecision:
    return ImplicitCreationDecision(False, "denied by deny-all guard")

def _check_none_guard(requested_type: type[Any]) -> ImplicitCreationDecision:
    return ImplicitCreationDecision(True, "allowed")
