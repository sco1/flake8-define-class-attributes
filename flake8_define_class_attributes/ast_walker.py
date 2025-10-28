from __future__ import annotations

import ast
import typing as t
from functools import lru_cache

AST_FUNC_NODES_T: t.TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef
AST_DEF_NODES_T: t.TypeAlias = AST_FUNC_NODES_T | ast.ClassDef
AST_ASSIGN_NODES_T: t.TypeAlias = ast.Assign | ast.AnnAssign | ast.AugAssign


class ResolvedCallError(Exception): ...  # noqa: D101


@t.runtime_checkable
class HasLoc(t.Protocol):  # noqa: D101
    lineno: int
    col_offset: int


def has_special_decorator(node: AST_FUNC_NODES_T) -> bool:
    """Return `True` if the node is decorated with `@classmethod` or `@staticmethod`."""
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            if d.id in {"classmethod", "staticmethod"}:
                return True

    return False


class AssignSpec(t.NamedTuple):
    """
    Helper container for an assignment statement's leftmost components.

    For non-attribute assignment (e.g. `a = 5` or `a[1] = 5`), the `attr` component should be passed
    as an empty string (`""`).
    """

    base: str
    attr: str


class SelfAssignNode(t.NamedTuple):
    """
    Helper container for a class or instance attribute that contains its associated node location.

    If this is instaniated, it is assumed that the containing class defines this variable as either
    a class attribute or an instance attribute in `__init__` and/or `__post_init__`.
    """

    attr: str
    lineno: int
    col_offset: int
    end_lineno: int | None
    end_col_offset: int | None

    @classmethod
    def from_node(cls, attr: str, node: AST_ASSIGN_NODES_T) -> SelfAssignNode:
        """
        Build an `SelfAssignNode` instance from the provided assignment node.

        NOTE: In cases where an assignment statement has multiple targets (e.g. `a,b = c`), location
        information for the extracted assignment targets will all share that of the base assignment
        node.
        """
        return cls(
            attr=attr,
            lineno=node.lineno,
            col_offset=node.col_offset,
            end_lineno=node.end_lineno,
            end_col_offset=node.end_col_offset,
        )


def resolve_attribute(base_node: ast.Attribute) -> AssignSpec:
    """
    Resolve the two leftmost components of the provided `Attribute` node.

    For example, the following nodes should all resolve to `AssignSpec("self", "a")`:

    ```
    self.a = 42
    self.a[1] = 42
    self.a.b = 42
    self.a.b[1].c.d = 42
    self.a.b.c.d.e.f.g = 42
    ```
    """
    # With nested attribute access, the leftmost components that we're interested in end up being
    # at the deepest part of the base node's value component, so we have to go spelunking
    node: ast.AST = base_node
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            node = node.value
        else:
            node = node.value

    # If we've gotten here, we should either have the base node in the simple case, or the leftmost
    # attribute access of a nested node
    if isinstance(node, ast.Name):
        return AssignSpec(node.id, attr)
    elif isinstance(node, ast.Call):
        # Raise here so we can ignore function calls upstream, e.g. self.foo().bar = 5
        # Seems easiest to control via exception rather than monkeying with the resolver return
        raise ResolvedCallError()
    else:
        # Not sure if this can actually be reached
        raise ValueError(
            f"{base_node.lineno}:{base_node.col_offset} Unexpected node type: {type(node)}"
        )


def resolve_assign(node: ast.AST) -> set[AssignSpec]:
    """
    Resolve an assignment statement into its lefmost components.

    Top level calls are expected to pass an instance of `ast.Assign`, `ast.AnnAssign`, or
    `ast.AugAssign`.
    """
    assigned = set()
    match node:
        case ast.Assign():
            for n in node.targets:
                assigned.update(resolve_assign(n))
        case ast.AnnAssign() | ast.AugAssign():
            assigned.update(resolve_assign(node.target))
        case ast.Tuple() | ast.List():
            for n in node.elts:
                assigned.update(resolve_assign(n))
        case ast.Attribute():
            assigned.add(resolve_attribute(node))
        case ast.Name():
            assigned.add(AssignSpec(node.id, ""))
        case ast.Subscript() | ast.Starred():
            assigned.update(resolve_assign(node.value))
        case _:
            msg_base = f"Unexpected node type: {type(node)}"
            if isinstance(node, HasLoc):
                msg = f"{node.lineno}:{node.col_offset} {msg_base}"
            else:
                msg = msg_base

            raise ValueError(msg)

    return assigned


@lru_cache
def resolve_instance_name(node: AST_FUNC_NODES_T) -> str:
    """Resolve the name of the instance variable of a class method, assumed to be the first var."""
    # Probably a needless optimization, but use a function so we can cache since this is being
    # called for each variable within a function's context
    return node.args.args[0].arg


class FDCAVisitor(ast.NodeVisitor):
    """
    Subclass `ast.NodeVisitor` to visit class definitions & extract assignment statements.

    As the class definition is walked, assignment statements are extracted into `AssignNode`
    instances, which contain information on the assignment as well as its source location.

    Extracted assignments are grouped as follows:
        * `class_vars` - Class-level attribute definitions
        * `init_vars` - Class attributes defined in `__init__` or `__post_init__`
        * `method_vars` - Class attributes defined in methods (`@classmethod` and `@staticmethod`
        are ignored)
    """

    _context: list[AST_DEF_NODES_T]
    _n_contained_classdef: int

    class_vars: set[str]
    init_vars: set[str]
    method_vars: list[SelfAssignNode]

    def __init__(self) -> None:
        self._context = []
        self._n_contained_classdef = 0

        self.class_vars = set()
        self.init_vars = set()
        self.method_vars = []

    @property
    def _n_function_levels(self) -> int:
        """
        Depth of current context from the most recent `ClassDef`.

        Returns `None` if no `ClassDef` is contained in context
        """
        depth = 0
        for node in reversed(self._context):
            if isinstance(node, ast.ClassDef):
                return depth

            depth += 1

        # Included for completeness. This should already guarded upstream & is only called if the
        # context tree contains at least one ClassDef node
        raise RuntimeError("Attempted to find depth from ClassDef with none in context")

    def switch_context(self, node: AST_DEF_NODES_T) -> None:
        """Keep track of class & function context to assist with dispatching walk behavior."""
        is_classdef = isinstance(node, ast.ClassDef)
        if is_classdef:  # For downstream bookkeeping so we don't have to iterate through _context
            self._n_contained_classdef += 1

        if (not is_classdef) and (self._n_contained_classdef > 0):
            if has_special_decorator(node):  # type: ignore[arg-type]  # Already narrowed
                # Skip classmethod & staticmethod
                return

        self._context.append(node)
        self.generic_visit(node)
        popped = self._context.pop()

        if isinstance(popped, ast.ClassDef):
            self._n_contained_classdef -= 1

    def visit_assign(self, node: AST_ASSIGN_NODES_T) -> None:
        """
        Visit an assignment statement and store it if relevant.

        Extracted assignments are grouped as follows:
            * `class_vars` - Class-level attribute definitions
            * `init_vars` - Class attributes defined in `__init__` or `__post_init__`
            * `method_vars` - Class attributes defined in methods (`@classmethod` and
            `@staticmethod` are ignored)
        """
        # Rather than checking if any context is a classdef, we have a bookkeeping counter upstream
        if self._n_contained_classdef == 0:
            return

        # Skip instances where the resolved assignment utilizes a function call, e.g.
        # self.foo().bar = 5
        try:
            new_nodes = resolve_assign(node)
        except ResolvedCallError:
            return

        if isinstance(self._context[-1], ast.ClassDef):
            self.class_vars.update(s.base for s in new_nodes)
        else:
            # To account for nested function scoping, determine the depth of the current node and
            # use the one whose parent context is the containing ClassDef node. This should
            # hopefully end up being the function that accepts the instance variable.
            # This isn't perfect, e.g. things might go badly if the nested function accepts the
            # instance under a new name, but I think it should do well for most projects?
            method_level = self._context[-self._n_function_levels]

            instance_varname = resolve_instance_name(method_level)
            self_nodes = (n for n in new_nodes if n.base == instance_varname)

            method_name = method_level.name
            if method_name in {"__init__", "__post_init__"}:
                self.init_vars.update(s.attr for s in self_nodes)
            else:
                # Retain node location information for methods so we can emit errors downstream
                self.method_vars.extend(
                    (SelfAssignNode.from_node(s.attr, node) for s in self_nodes)
                )

    visit_FunctionDef = switch_context
    visit_AsyncFunctionDef = switch_context
    visit_ClassDef = switch_context

    visit_Assign = visit_assign
    visit_AnnAssign = visit_assign
    visit_AugAssign = visit_assign
