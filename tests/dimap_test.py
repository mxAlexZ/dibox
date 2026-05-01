from typing import Any, Union

import pytest

from dibox.dimap import ANY_ARG, ANY_TYPE, DIMap, MatchResult, TypeQuery, WildArgName


class Bar:
    ...

class Foo:
    ...

class Rando:
    ...


class DIMapTest:
    @pytest.mark.parametrize(
        ("type", "arg", "expected"),
        [
            (Bar, "arg", ("bar/arg", (Bar, "arg"))),
            (Bar, "rando", ("bar/none", (Bar, ANY_ARG))),
            (Foo, "rando", ("foo/none", (Foo, ANY_ARG))),
            (Rando | Foo, "rando", ("foo/none", (Foo, ANY_ARG))),
            (Union[Rando, Bar], "rando", ("bar/none", (Bar, ANY_ARG))),
            (Rando, "arg", ("none/arg", (ANY_TYPE, "arg"))),
            (Rando, "rando", (None, (ANY_TYPE, ANY_ARG))),
        ],
    )
    def test_find_match(self, type: TypeQuery[Any], arg: WildArgName, expected: MatchResult[str, Any]):
        m = DIMap[str]()
        m[(Bar, ANY_ARG)] = "bar/none"
        m[(ANY_TYPE, "arg")] = "none/arg"
        m[(Bar, "arg")] = "bar/arg"
        m[(Foo, ANY_ARG)] = "foo/none"

        assert m.find_match(type, arg) == expected
