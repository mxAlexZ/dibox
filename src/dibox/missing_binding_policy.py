from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import UUID

TypePredicate = Callable[[type[Any]], bool]

PolicyPreset = Literal["open", "explicit-roots", "closed"]

_VALUE_TYPES = (str, int, float, bool, bytes, list, dict, set, tuple, Path, Decimal, UUID)


@dataclass(slots=True)
class MissingBindingDecision:
    allowed: bool
    reason: str


@dataclass(slots=True)
class MissingBindingRule:
    matches: TypePredicate
    name: str


class MissingBindingPolicy:
    """Controls which unbound concrete types DIBox may create implicitly."""

    def __init__(
        self,
        roots: Literal["create-implicitly", "require-binding"] = "create-implicitly",
        unmatched_dependencies: Literal["create-implicitly", "require-allow-rule"] = "create-implicitly",
    ) -> None:
        self.allow_rules: list[MissingBindingRule] = []
        self.deny_rules: list[MissingBindingRule] = []
        self._require_binding_for_roots = roots == "require-binding"
        self._require_allow_rule_for_dependencies = unmatched_dependencies == "require-allow-rule"

    @classmethod
    def from_preset(cls, preset: PolicyPreset) -> "MissingBindingPolicy":
        match preset:
            case "open":
                return cls()
            case "explicit-roots":
                return cls(roots="require-binding")
            case "closed":
                return cls(roots="require-binding", unmatched_dependencies="require-allow-rule")
            case _:
                raise ValueError(f"unknown preset {preset!r}")

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

    def decide(self, requested_type: object, is_root: bool) -> MissingBindingDecision:
        """Return whether requested_type may be created implicitly."""
        if not isinstance(requested_type, type):
            return MissingBindingDecision(False, "denied because request is not a concrete class")
        if is_root and self._require_binding_for_roots:
            return MissingBindingDecision(False, "denied because root requires explicit binding")
        denied_by = _match_rules(self.deny_rules, requested_type)
        if denied_by is not None:
            return MissingBindingDecision(False, f'denied by rule "{denied_by.name}"')
        allowed_by = _match_rules(self.allow_rules, requested_type)
        if allowed_by is not None:
            return MissingBindingDecision(True, f'allowed by rule "{allowed_by.name}"')
        if self._require_allow_rule_for_dependencies:
            return MissingBindingDecision(False, "denied because unmatched dependency requires an allow rule")
        if requested_type in _VALUE_TYPES:
            return MissingBindingDecision(False, "denied by value-types guard")
        return MissingBindingDecision(True, "allowed")


def _make_package_rule(packages: tuple[str, ...], name: str | None) -> MissingBindingRule:
    if not packages:
        raise ValueError("at least one package is required")
    if any(not package for package in packages):
        raise ValueError("package names must not be empty")
    rule_name = name or f"package {', '.join(packages)}"
    return MissingBindingRule(
        lambda req_type: any(
            req_type.__module__ == package or req_type.__module__.startswith(f"{package}.")
            for package in packages
        ),
        rule_name,
    )

def _make_predicate_rule(predicate: TypePredicate, name: str | None) -> MissingBindingRule:
    rule_name = name or getattr(predicate, "__name__", None) or str(predicate)
    return MissingBindingRule(predicate, rule_name)

def _make_type_rule(types: tuple[type[Any], ...], name: str | None) -> MissingBindingRule:
    if not types:
        raise ValueError("at least one type is required")
    rule_name = name or f"type {', '.join(t.__name__ for t in types)}"
    return MissingBindingRule(lambda req_type: any(req_type is t for t in types), rule_name)

def _match_rules(rules: list[MissingBindingRule], requested_type: type[Any]) -> MissingBindingRule | None:
    return next((rule for rule in rules if rule.matches(requested_type)), None)
