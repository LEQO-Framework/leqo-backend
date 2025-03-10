from textwrap import dedent


def normalize(program: str) -> str:
    """Normalize QASM-string."""
    return dedent(program).strip()
