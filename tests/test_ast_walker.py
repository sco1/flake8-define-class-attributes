import ast

import pytest

from flake8_define_class_attributes.ast_walker import (
    AssignNode,
    AssignSpec,
    has_special_decorator,
    resolve_assign,
    resolve_attribute,
)
from tests import ASSIGN_NODE_P


def test_assignnode_eq() -> None:
    left = AssignNode(
        spec=AssignSpec("a", "b"), lineno=1, col_offset=2, end_lineno=None, end_col_offset=None
    )
    right = AssignNode(
        spec=AssignSpec("a", "b"), lineno=3, col_offset=4, end_lineno=None, end_col_offset=None
    )

    assert left == right


def test_assignmode_hash() -> None:
    spec = AssignSpec("a", "b")
    node = AssignNode(spec=spec, lineno=1, col_offset=2, end_lineno=None, end_col_offset=None)
    assert hash(node) == hash(spec)


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


ASSIGN_TEST_CASES = (
    ("a = 42", {AssignSpec("a", "")}),
    ("a[1] = 42", {AssignSpec("a", "")}),
    ("a += 42", {AssignSpec("a", "")}),
    ("a[1] += 42", {AssignSpec("a", "")}),
    ("a, b = 42, 13", {AssignSpec("a", ""), AssignSpec("b", "")}),
    ("_, b = 42, 13", {AssignSpec("_", ""), AssignSpec("b", "")}),
    ("a, *b = [42, 13, 7]", {AssignSpec("a", ""), AssignSpec("b", "")}),
    ("self.a = 42", {AssignSpec("self", "a")}),
    ("_, self.b = 42, 13", {AssignSpec("_", ""), AssignSpec("self", "b")}),
    ("self.a, self.b = 42, 13", {AssignSpec("self", "a"), AssignSpec("self", "b")}),
    ("self.a, b = 42, 13", {AssignSpec("self", "a"), AssignSpec("b", "")}),
    ("self.a[1] = 42", {AssignSpec("self", "a")}),
    ("self.a += 42", {AssignSpec("self", "a")}),
    ("self.a[1] += 42", {AssignSpec("self", "a")}),
)


@pytest.mark.parametrize(("src", "truth_out"), ASSIGN_TEST_CASES)
def test_resolve_assign(src: str, truth_out: set[AssignSpec]) -> None:
    tree = ast.parse(src)
    node = tree.body[0]

    assert resolve_assign(node) == truth_out


ASSIGN_NODE_TEST_CASES = (
    ("a = 42", {ASSIGN_NODE_P(spec=AssignSpec("a", ""))}),
    (
        "a, b = 42, 13",
        {ASSIGN_NODE_P(spec=AssignSpec("a", "")), ASSIGN_NODE_P(spec=AssignSpec("b", ""))},
    ),
)


@pytest.mark.parametrize(("src", "truth_out"), ASSIGN_NODE_TEST_CASES)
def test_assign_node(src: str, truth_out: set[AssignNode]) -> None:
    tree = ast.parse(src)
    node = tree.body[0]

    assert AssignNode.from_node(node) == truth_out  # type: ignore[arg-type]


def test_fake_class_var() -> None:
    node = AssignNode(
        spec=AssignSpec("self", "a"), lineno=1, col_offset=2, end_lineno=None, end_col_offset=None
    )

    TRUTH_OUT = AssignNode(
        spec=AssignSpec("a", ""), lineno=1, col_offset=2, end_lineno=None, end_col_offset=None
    )

    assert node.as_fake_class_var() == TRUTH_OUT
