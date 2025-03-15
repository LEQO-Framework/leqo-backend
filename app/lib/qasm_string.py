import re

REMOVE_INDENT = re.compile(r"\n +", re.MULTILINE)


def normalize(program: str) -> str:
    """Normalize QASM-string."""
    return REMOVE_INDENT.sub("\n", program).strip()
