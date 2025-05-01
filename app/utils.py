"""
Utils used throughout the whole application.
"""

from collections.abc import Callable
from typing import TypeVar

TParam = TypeVar("TParam")
TReturn = TypeVar("TReturn")


def opt_call(func: Callable[[TParam], TReturn], arg: TParam | None) -> TReturn | None:
    """
    Optional chaining for function calls.

    :param func: Function to call if arg is not None
    :param arg: Argument to pass to func
    :return: Result of func or None
    """

    if arg is None:
        return None

    return func(arg)


T = TypeVar("T")


def not_none_or(value: T | None, default_value: T) -> T:
    """
    Nullish coalescence - `??` operator.
    Returns `value` if not `None`.
    Else, returns `default_value`.
    """

    if value is None:
        return default_value

    return value
