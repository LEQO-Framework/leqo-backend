from typing import override


class SingleQubitInputInfo:
    id: int
    position: int

    def __init__(self, input_id: int, position: int) -> None:
        self.id = input_id
        self.position = position


class SingleQubitOutputInfo:
    id: int
    position: int

    def __init__(self, output_id: int, position: int) -> None:
        self.id = output_id
        self.position = position


class SingleQubitIOInfo:
    input: SingleQubitInputInfo | None
    output: SingleQubitOutputInfo | None
    reusable: bool


class IOInfo:
    declaration_to_id: dict[str, list[int]]
    id_to_info: dict[int, SingleQubitIOInfo]

    def __init__(
        self,
        declaration_to_id: dict[str, list[int]] | None = None,
        id_to_info: dict[int, SingleQubitIOInfo] | None = None,
    ) -> None:
        self.declaration_to_id = declaration_to_id or {}
        self.id_to_info = id_to_info or {}

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, IOInfo):
            return False
        return (
            self.declaration_to_id == value.declaration_to_id
            and self.id_to_info == value.id_to_info
        )
