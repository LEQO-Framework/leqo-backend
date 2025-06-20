"""
Utils for the :mod:`app.processing.merge` module.
"""

from app.processing.utils import ProcessingException


# has to be defined in separate file because of circular imports
# between merge/__init__.py and merge/connections.py
class MergeException(ProcessingException):
    """
    Exception raises during :mod:`app.processing.merge`.
    """
