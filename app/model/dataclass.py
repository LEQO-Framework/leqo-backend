from dataclasses import dataclass


@dataclass()
class SingleInputInfo:
    id: int
    position: int


@dataclass()
class SingleOutputInfo:
    id: int
    position: int


@dataclass()
class SingleIOInfo:
    input: SingleInputInfo | None
    output: SingleOutputInfo | None
    reusable: bool

    def __init__(
        self,
        input: SingleInputInfo | None = None,
        output: SingleOutputInfo | None = None,
        reusable: bool | None = None,
    ) -> None:
        self.input = input
        self.output = output
        self.reusable = reusable or False


@dataclass()
class SnippetIOInfo:
    declaration_to_id: dict[str, list[int]]
    alias_to_id: dict[str, list[int]]
    id_to_info: dict[int, SingleIOInfo]

    def __init__(
        self,
        declaration_to_id: dict[str, list[int]] | None = None,
        alias_to_id: dict[str, list[int]] | None = None,
        id_to_info: dict[int, SingleIOInfo] | None = None,
    ) -> None:
        self.declaration_to_id = declaration_to_id or {}
        self.alias_to_id = alias_to_id or {}
        self.id_to_info = id_to_info or {}


@dataclass()
class IOInfo:
    snippets: list[SnippetIOInfo]

    def __init__(self, snippets: list[SnippetIOInfo] | None = None) -> None:
        self.snippets = snippets or []
