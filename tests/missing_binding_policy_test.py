from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from dibox import ANY_TYPE, MissingBindingPolicy


class _Foo:
    pass


class _FooRequired:
    def __init__(self, dependency: object):
        self.dependency = dependency


class MissingBindingPolicyTest:
    def test_deny_rules_take_precedence_over_allow_rules(self):
        policy = MissingBindingPolicy()
        policy.allow_type(_Foo, name="application leaf")
        policy.deny_type(_Foo, name="blocked leaf")

        decision = policy.decide(_Foo, False)

        assert not decision.allowed
        assert decision.reason == 'denied by rule "blocked leaf"'


    def test_allow_rule_authorizes_dependency_when_required(self):
        policy = MissingBindingPolicy(unmatched_dependencies="require-allow-rule")
        policy.allow_type(_Foo)

        assert policy.decide(_Foo, False).allowed


    def test_package_rules_match_package_boundaries_and_subpackages(self):
        policy = MissingBindingPolicy(unmatched_dependencies="require-allow-rule")
        policy.allow_package("my_app")

        assert policy.decide(_make_type(module="my_app"), False).allowed
        assert policy.decide(_make_type(module="my_app.subpackage"), False).allowed
        assert not policy.decide(_make_type(module="my_application"), False).allowed


    def test_deny_package_rule_overrides_broader_allow_package_rule(self):
        policy = MissingBindingPolicy()
        policy.allow_package("my_app")
        policy.deny_package("my_app.excluded")

        decision = policy.decide(_make_type(module="my_app.excluded"), False)

        assert not decision.allowed
        assert decision.reason == 'denied by rule "package my_app.excluded"'


    def test_allow_if_uses_explicit_rule_name_in_reason(self):
        policy = MissingBindingPolicy(unmatched_dependencies="require-allow-rule")
        policy.allow_if(lambda type_to_match: type_to_match is _Foo, name="test leaf")

        decision = policy.decide(_Foo, False)

        assert decision.allowed
        assert decision.reason == 'allowed by rule "test leaf"'


    def test_deny_if_uses_explicit_rule_name_in_reason(self):
        policy = MissingBindingPolicy()
        policy.deny_if(lambda type_to_match: type_to_match is _Foo, name="test leaf")

        decision = policy.decide(_Foo, False)

        assert not decision.allowed
        assert decision.reason == 'denied by rule "test leaf"'


    @pytest.mark.parametrize(
        "requested_type",
        ["not a type", int | str, list[str], dict[str, int], tuple[int, int], ANY_TYPE],
    )
    def test_non_concrete_request_is_denied(self, requested_type: object):
        decision = MissingBindingPolicy().decide(requested_type, False)

        assert not decision.allowed
        assert decision.reason == "denied because request is not a concrete class"


    @pytest.mark.parametrize(
        "value_type",
        [str, int, float, bool, bytes, list, dict, set, tuple, Path, Decimal, UUID],
    )
    def test_builtin_value_type_rejection_denies_known_value_types(self, value_type: type[object]):
        decision = MissingBindingPolicy().decide(value_type, False)

        assert not decision.allowed
        assert decision.reason == "denied by value-types guard"


    def test_builtin_value_type_rejection_does_not_block_other_classes(self):
        assert MissingBindingPolicy().decide(_Foo, False).allowed


    @pytest.mark.parametrize("unmatched_type", [_Foo, _FooRequired])
    def test_unmatched_dependencies_require_allow_rule_when_configured(
        self,
        unmatched_type: type[object],
    ):
        decision = MissingBindingPolicy(unmatched_dependencies="require-allow-rule").decide(unmatched_type, False)

        assert not decision.allowed
        assert decision.reason == "denied because unmatched dependency requires an allow rule"


    def test_default_policy_allows_unmatched_dependencies(self):
        policy = MissingBindingPolicy()

        assert policy.decide(_FooRequired, False).allowed


    def test_decide_propagates_predicate_exceptions(self):
        def broken_predicate(_type_to_match: type[object]) -> bool:
            raise TypeError("broken predicate")

        policy = MissingBindingPolicy()
        policy.deny_if(broken_predicate)

        with pytest.raises(TypeError, match="broken predicate"):
            policy.decide(_Foo, False)


    def test_package_rules_require_at_least_one_non_empty_package(self):
        policy = MissingBindingPolicy()

        with pytest.raises(ValueError, match="at least one package"):
            policy.allow_package()
        with pytest.raises(ValueError, match="must not be empty"):
            policy.deny_package("")


    def test_type_rules_require_at_least_one_type(self):
        policy = MissingBindingPolicy()

        with pytest.raises(ValueError, match="at least one type"):
            policy.allow_type()
        with pytest.raises(ValueError, match="at least one type"):
            policy.deny_type()


class MissingBindingPolicyRootsSwitchTest:
    def test_require_binding_blocks_implicit_root_creation(self):
        policy = MissingBindingPolicy(roots="require-binding")

        decision = policy.decide(_Foo, is_root=True)

        assert not decision.allowed
        assert decision.reason == "denied because root requires explicit binding"

    def test_require_binding_applies_only_at_request_boundary(self):
        policy = MissingBindingPolicy(roots="require-binding")

        assert policy.decide(_Foo, is_root=False).allowed

    def test_create_implicitly_allows_implicit_root_creation(self):
        policy = MissingBindingPolicy(roots="create-implicitly")

        assert policy.decide(_Foo, is_root=True).allowed

class MissingBindingPolicyPresetTest:
    def test_open_preset_allows_implicit_roots_and_dependencies(self):
        policy = MissingBindingPolicy.from_preset("open")

        assert policy.decide(_Foo, is_root=True).allowed
        assert policy.decide(_Foo, is_root=False).allowed

    def test_explicit_roots_preset_requires_root_bindings_only(self):
        policy = MissingBindingPolicy.from_preset("explicit-roots")

        assert not policy.decide(_Foo, is_root=True).allowed
        assert policy.decide(_Foo, is_root=False).allowed

    def test_closed_preset_requires_root_binding_and_dependency_allow_rule(self):
        policy = MissingBindingPolicy.from_preset("closed")

        assert not policy.decide(_Foo, is_root=True).allowed
        assert not policy.decide(_Foo, is_root=False).allowed

    def test_closed_preset_allows_dependency_when_allow_rule_matches(self):
        policy = MissingBindingPolicy.from_preset("closed")
        policy.allow_type(_Foo)

        assert policy.decide(_Foo, is_root=False).allowed

    def test_unknown_preset_is_rejected(self):
        with pytest.raises(ValueError, match="unknown preset"):
            MissingBindingPolicy.from_preset("unknown")  # type: ignore[arg-type]


def _make_type(module: str) -> type[object]:
    class _Type:
        pass
    _Type.__module__ = module
    return _Type
