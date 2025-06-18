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


def not_none[T](value: T | None, error_msg: str) -> T:
    """
    Returns value if not none or raises exception.

    :param value: Value to check.
    :param error_msg: Message to throw.
    :return: The none-none value.
    """

    if value is None:
        raise Exception(error_msg)

    return value


def not_none_or[T](value: T | None, default_value: T) -> T:
    """
    Nullish coalescence - `??` operator.
    Returns `value` if not `None`.
    Else, returns `default_value`.
    """

    if value is None:
        return default_value

    return value


def duplicates[T](list: list[T]) -> set[T]:
    """
    Returns set of duplicate items.
    """
    seen = set()
    result = set()
    for item in list:
        if item in seen:
            result.add(item)
        else:
            seen.add(item)
    return result
