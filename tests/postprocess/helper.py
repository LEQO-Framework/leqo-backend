from textwrap import dedent


def normalize(program: str) -> str:
    return dedent(program).strip()
