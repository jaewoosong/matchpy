# -*- coding: utf-8 -*-
import itertools
from typing import Callable, List, NamedTuple, Sequence, Tuple, Union

from .expressions import Expression, Operation, Substitution, Variable
from .matching.one_to_one import match


def substitute(expression: Expression, substitution: Substitution) -> Tuple[Union[Expression, List[Expression]], bool]:
    """Replaces variables in the given `expression` by the given `substitution`.

    In addition to the resulting expression(s), a bool is returned indicating whether anything was substituted.
    If nothing was substituted, the original expression is returned.
    Not that this function returns a list of expressions iff the expression is a variable and its substitution
    is a list of expressions. In other cases were a substitution is a list of expressions, the expressions will
    be integrated as operands in the surrounding operation:

    >>> substitute(f(x_, c), {'x': [a, b]})
    (f(Symbol('a'), Symbol('b'), Symbol('c')), True)

    Parameters:
        expression:
            An expression in which variables are substituted.
        substitution:
            A substitution dictionary. The key is the name of the variable,
            the value either an expression or a list of expression to use as a replacement for
            the variable.

    Returns:
        The expression resulting from applying the substitution.
    """
    if isinstance(expression, Variable):
        if expression.name in substitution:
            return substitution[expression.name], True
    elif isinstance(expression, Operation):
        any_replaced = False
        new_operands = []
        for operand in expression.operands:
            result, replaced = substitute(operand, substitution)
            if replaced:
                any_replaced = True
            if isinstance(result, (list, tuple)):
                new_operands.extend(result)
            else:
                new_operands.append(result)
        if any_replaced:
            return type(expression).from_args(*new_operands), True

    return expression, False


def replace(expression: Expression, position: Sequence[int], replacement: Union[Expression, List[Expression]]) \
        -> Union[Expression, List[Expression]]:
    r"""Replaces the subexpression of `expression` at the given `position` with the given `replacement`.

    The original `expression` itself is not modified, but a modified copy is returned. If the replacement
    is a list of expressions, it will be expanded into the list of operands of the respective operation:

    >>> replace(f(a), (0, ), [b, c])
    f(Symbol('b'), Symbol('c'))

    Parameters:
        expression:
            An :class:`Expression` where a (sub)expression is to be replaced.
        position:
            A tuple of indices, e.g. the empty tuple refers to the `expression` itself,
            `(0, )` refers to the first child (operand) of the `expression`, `(0, 0)` to the first
            child of the first child etc.
        replacement:
            Either an :class:`Expression` or a list of :class:`Expression`\s to be
            inserted into the `expression` instead of the original expression at that `position`.

    Returns:
        The resulting expression from the replacement.
    """
    if position == ():
        return replacement
    if not isinstance(expression, Operation):
        raise IndexError("Invalid position {!r} for expression {!s}".format(position, expression))
    if position[0] >= len(expression.operands):
        raise IndexError("Position {!r} out of range for expression {!s}".format(position, expression))
    op_class = type(expression)
    pos = position[0]
    subexpr = replace(expression.operands[pos], position[1:], replacement)
    if isinstance(subexpr, list):
        return op_class.from_args(*(expression.operands[:pos] + subexpr + expression.operands[pos+1:]))
    operands = expression.operands.copy()
    operands[pos] = subexpr
    return op_class.from_args(*operands)

ReplacementRule = NamedTuple('ReplacementRule', [('pattern', Expression), ('replacement', Callable[..., Expression])])


def replace_all(expression: Expression, rules: Sequence[ReplacementRule]) -> Union[Expression, List[Expression]]:
    grouped = itertools.groupby(rules, lambda r: r.pattern.head)
    heads, tmp_groups = map(list, zip(*[(h, list(g)) for h, g in grouped]))
    groups = [list(g) for g in tmp_groups]
    replaced = True
    while replaced:
        replaced = False
        for head, group in zip(heads, groups):
            predicate = None
            if head is not None:
                predicate = lambda e: e.head == head
            for subexpr, pos in expression.preorder_iter(predicate):
                for pattern, replacement in group:
                    try:
                        subst = next(match(subexpr, pattern))
                        result = replacement(**subst)
                        expression = replace(expression, pos, result)
                        replaced = True
                        break
                    except StopIteration:
                        pass
                if replaced:
                    break
            if replaced:
                break

    return expression
