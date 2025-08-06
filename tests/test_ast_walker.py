import ast

import pytest

from flake8_define_class_attributes.ast_walker import (
    AssignSpec,
    has_special_decorator,
    resolve_attribute,
)

DECORATOR_TEST_CASES = (
    ("@classmethod\ndef foo(self): ...", True),
    ("@staticmethod\ndef foo(self): ...", True),
    ("def foo(self): ...", False),
    ("@property\ndef foo(self): ...", False),
    ("@lru_cache\ndef foo(self): ...", False),
    ("@lru_cache(maxsize=128)\ndef foo(self): ...", False),
    ("@functools.lru_cache\ndef foo(self): ...", False),
    ("@functools.lru_cache(maxsize=128)\ndef foo(self): ...", False),
)


@pytest.mark.parametrize(("src", "truth_out"), DECORATOR_TEST_CASES)
def test_has_special_decorator(src: str, truth_out: bool) -> None:
    tree = ast.parse(src)
    function_node = tree.body[0]

    assert has_special_decorator(function_node) == truth_out  # type: ignore[arg-type]


ATTRIBUTE_TEST_CASES = (
    ("self.a = 42", AssignSpec("self", "a")),
    ("self.a[1] = 42", AssignSpec("self", "a")),
    ("self.a.b = 42", AssignSpec("self", "a")),
    ("self.a.b[1].c.d = 42", AssignSpec("self", "a")),
    ("self.a.b.c.d.e.f.g = 42", AssignSpec("self", "a")),
)


@pytest.mark.parametrize(("src", "truth_out"), ATTRIBUTE_TEST_CASES)
def test_resolve_attribute(src: str, truth_out: AssignSpec) -> None:
    tree = ast.parse(src)
    assignment_target = tree.body[0].targets[0]  # type: ignore[attr-defined]

    assert resolve_attribute(assignment_target) == truth_out
