from typing import Any, Union

import pytest

from dibox.dimap import DIMap, MatchResult


class Bar: ...


class Foo: ...


class Rando: ...


class DIMapTest:
    @pytest.mark.parametrize(
        ("type", "arg", "expected"),
        [
            (Bar, "arg", ("bar/arg", (Bar, "arg"))),
            (Bar, "rando", ("bar/none", (Bar, None))),
            (Foo, "rando", ("foo/none", (Foo, None))),
            (Foo | Rando, "rando", ("foo/none", (Foo, None))),
            (Union[Bar, Rando], "rando", ("bar/none", (Bar, None))),
            (Rando, "arg", ("none/arg", (None, "arg"))),
            (Rando, "rando", None),
        ],
    )
    def test_find_match(self, type: type[Any] | None, arg: str | None, expected: MatchResult[str, Any]):
        m = DIMap[str]()
        m[(Bar, None)] = "bar/none"
        m[(None, "arg")] = "none/arg"
        m[(Bar, "arg")] = "bar/arg"
        m[(Foo, None)] = "foo/none"

        assert m.find_match(type, arg) == expected
