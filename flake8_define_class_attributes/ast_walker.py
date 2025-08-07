from __future__ import annotations

import ast
import typing as t

AST_FUNC_NODES_T: t.TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef
AST_DEF_NODES_T: t.TypeAlias = AST_FUNC_NODES_T | ast.ClassDef
AST_ASSIGN_NODES_T: t.TypeAlias = ast.Assign | ast.AnnAssign | ast.AugAssign


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


class AssignNode(t.NamedTuple):
    """
    Helper container for `AssignSpec` that contains its associated node location.

    NOTE: For downstream convenience, `AssignNode`'s `__eq__` and `__hash__` operations have been
    modified to only consider `AssignNode.spec`.
    """

    spec: AssignSpec
    lineno: int
    col_offset: int
    end_lineno: int | None
    end_col_offset: int | None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AssignNode):
            return NotImplemented

        return self.spec == other.spec

    def __hash__(self) -> int:
        return hash(self.spec)

    @classmethod
    def from_node(cls, node: AST_ASSIGN_NODES_T) -> set[AssignNode]:
        """
        Build an `AssignNode` instance from the provided assignment statement.

        NOTE: In cases where an assignment statement has multiple targets (e.g. `a,b = c`), location
        information for the extracted assignment targets will all share that of the base assignment
        node.
        """
        specs = resolve_assign(node)
        # For now make the assignments share the base node's location information
        # In the future it would probably be better to use the location from each target node but
        # right now we're not preserving that during resolution
        return {
            cls(
                spec=s,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
            )
            for s in specs
        }

    def as_fake_class_var(self) -> AssignNode:
        """
        Return a new `AssignNode` instance whose `spec` is transformed to emulate a class variable.

        For exampale, `AssignSpec("self", "a")` -> `AssignSpec("a", "")`
        """
        spec, *rest = self
        spec = AssignSpec(spec.attr, "")
        return AssignNode(spec, *rest)  # type: ignore[arg-type]


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

    NOTE: Attribute extraction from methods currently assumes that `self` is declared as the
    instance variable. All other attribute access, as well as non-attribute assignment, is ignored.
    """

    _context: list[AST_DEF_NODES_T]
    _n_contained_classdef: int

    class_vars: set[AssignNode]
    init_vars: set[AssignNode]
    method_vars: set[AssignNode]

    def __init__(self) -> None:
        self._context = []
        self._n_contained_classdef = 0

        self.class_vars = set()
        self.init_vars = set()
        self.method_vars = set()

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

        NOTE: Attribute extraction from methods currently assumes that `self` is declared as the
        instance variable. All other attribute access, as well as non-attribute assignment, is
        ignored.
        """
        # Rather than checking if any context is a classdef, we have a bookkeeping counter upstream
        if self._n_contained_classdef == 0:
            return

        new_nodes = AssignNode.from_node(node)
        if isinstance(self._context[-1], ast.ClassDef):
            self.class_vars.update(new_nodes)
        else:
            self_nodes = (n for n in new_nodes if n.spec.base == "self")
            method_name = self._context[-1].name
            if method_name in {"__init__", "__post_init__"}:
                self.init_vars.update(self_nodes)
            else:
                self.method_vars.update(self_nodes)

    visit_FunctionDef = switch_context
    visit_AsyncFunctionDef = switch_context
    visit_ClassDef = switch_context

    visit_Assign = visit_assign
    visit_AnnAssign = visit_assign
    visit_AugAssign = visit_assign
