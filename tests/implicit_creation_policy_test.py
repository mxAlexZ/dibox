from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from dibox import ANY_TYPE, ImplicitCreationGuard, ImplicitCreationPolicy


class _ZeroDependencyClass:
    pass


class _RequiredDependencyClass:
    def __init__(self, dependency: object):
        self.dependency = dependency


class ImplicitCreationPolicyTest:
    def test_deny_type_rule_overrides_allow_rule(self):
        policy = ImplicitCreationPolicy()
        policy.allow_type(_ZeroDependencyClass, name="application leaf")
        policy.deny_type(_ZeroDependencyClass, name="blocked leaf")

        decision = policy.decide(_ZeroDependencyClass)

        assert not decision.allowed
        assert decision.reason == 'denied by rule "blocked leaf"'


    def test_allow_rule_overrides_guard(self):
        policy = ImplicitCreationPolicy(guard="deny-all")
        policy.allow_type(_ZeroDependencyClass)

        assert policy.decide(_ZeroDependencyClass).allowed


    def test_package_rule_matches_package_and_subpackage(self):
        policy = ImplicitCreationPolicy(guard="deny-all")
        policy.allow_package("my_app")

        assert policy.decide(_make_type(module="my_app")).allowed
        assert policy.decide(_make_type(module="my_app.subpackage")).allowed
        assert not policy.decide(_make_type(module="my_application")).allowed


    def test_deny_package_rule_for_subpackage_overrides_allow_rule(self):
        policy = ImplicitCreationPolicy()
        policy.allow_package("my_app")
        policy.deny_package("my_app.excluded")

        decision = policy.decide(_make_type(module="my_app.excluded"))

        assert not decision.allowed
        assert decision.reason == 'denied by rule "package my_app.excluded"'


    def test_allow_if_rule_with_explicit_name(self):
        policy = ImplicitCreationPolicy(guard="deny-all")
        policy.allow_if(lambda type_to_match: type_to_match is _ZeroDependencyClass, name="test leaf")

        decision = policy.decide(_ZeroDependencyClass)

        assert decision.allowed
        assert decision.reason == 'allowed by rule "test leaf"'


    def test_deny_if_rule_with_explicit_name(self):
        policy = ImplicitCreationPolicy(guard="none")
        policy.deny_if(lambda type_to_match: type_to_match is _ZeroDependencyClass, name="test leaf")

        decision = policy.decide(_ZeroDependencyClass)

        assert not decision.allowed
        assert decision.reason == 'denied by rule "test leaf"'


    @pytest.mark.parametrize(
        "requested_type",
        ["not a type", int | str, list[str], dict[str, int], tuple[int, int], ANY_TYPE],
    )
    def test_non_concrete_request_is_denied(self, requested_type: object):
        decision = ImplicitCreationPolicy().decide(requested_type)

        assert not decision.allowed
        assert decision.reason == "denied because request is not a concrete class"


    @pytest.mark.parametrize("value_type", [str, int, float, bool, bytes, list, dict, set, tuple, Path, Decimal, UUID])
    def test_value_types_guard_denies_known_value_types(self, value_type: type[object]):
        decision = ImplicitCreationPolicy().decide(value_type)

        assert not decision.allowed
        assert decision.reason == "denied by value-types guard"


    @pytest.mark.parametrize("unclassified_type", [_ZeroDependencyClass])
    def test_value_types_guard_allows_other_types(self, unclassified_type: type[object]):
        assert ImplicitCreationPolicy().decide(unclassified_type).allowed


    def test_zero_dependency_guard_distinguishes_constructor_requirements(self):
        policy = ImplicitCreationPolicy(guard="zero-dependency")

        assert not policy.decide(_ZeroDependencyClass).allowed
        assert policy.decide(_RequiredDependencyClass).allowed


    def test_zero_dependency_guard_denies_non_introspectable_type(self):
        policy = ImplicitCreationPolicy(guard="zero-dependency")

        decision = policy.decide(str)

        assert not decision.allowed
        assert decision.reason == "denied by zero-dependency guard"


    @pytest.mark.parametrize("unmatched_type", [_ZeroDependencyClass, _RequiredDependencyClass, str])
    def test_deny_all_guard_denies_all_unmatched_types(self, unmatched_type: type[object]):
        decision = ImplicitCreationPolicy(guard="deny-all").decide(unmatched_type)

        assert not decision.allowed
        assert decision.reason == "denied by deny-all guard"


    def test_none_guard_allows_all_types(self):
        policy = ImplicitCreationPolicy(guard="none")

        assert policy.decide(_ZeroDependencyClass).allowed
        assert policy.decide(_RequiredDependencyClass).allowed
        assert policy.decide(str).allowed


    @pytest.mark.parametrize(
        "guard_val",
        [
            ImplicitCreationGuard.NONE,
            ImplicitCreationGuard.VALUE_TYPES,
            ImplicitCreationGuard.ZERO_DEPENDENCY,
            ImplicitCreationGuard.DENY_ALL,
            "none",
            "value-types",
            "zero-dependency",
            "deny-all",
        ],
    )
    def test_constructor_accepts_guard_enum_and_literal(self, guard_val: Any):
        ImplicitCreationPolicy(guard=guard_val)


    def test_rejects_invalid_guard(self):
        with pytest.raises(ValueError, match="unknown"):
            ImplicitCreationPolicy(guard="unknown")  # type: ignore[arg-type]


    def test_decide_propagates_predicate_exceptions(self):
        def broken_predicate(_type_to_match: type[object]) -> bool:
            raise TypeError("broken predicate")

        policy = ImplicitCreationPolicy(guard="none")
        policy.deny_if(broken_predicate)

        with pytest.raises(TypeError, match="broken predicate"):
            policy.decide(_ZeroDependencyClass)


    def test_empty_package_rule_is_rejected(self):
        policy = ImplicitCreationPolicy()

        with pytest.raises(ValueError, match="at least one package"):
            policy.allow_package()
        with pytest.raises(ValueError, match="must not be empty"):
            policy.deny_package("")


    def test_empty_type_rule_is_rejected(self):
        policy = ImplicitCreationPolicy()

        with pytest.raises(ValueError, match="at least one type"):
            policy.allow_type()
        with pytest.raises(ValueError, match="at least one type"):
            policy.deny_type()


def _make_type(module: str) -> type[object]:
    class _Type:
        pass
    _Type.__module__ = module
    return _Type
