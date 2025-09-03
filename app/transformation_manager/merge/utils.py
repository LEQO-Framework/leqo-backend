"""
Utils for the :mod:`app.transformation_manager.merge` module.
"""

from app.transformation_manager.utils import ProcessingException


# has to be defined in separate file because of circular imports
# between merge/__init__.py and merge/connections.py
class MergeException(ProcessingException):
    """
    Exception raises during :mod:`app.transformation_manager.merge`.
    """
