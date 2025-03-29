from typing import override


class SingleQubitInputInfo:
    id: int
    position: int


class SingleQubitOutputInfo:
    id: int
    position: int


class SingleQubitIOInfo:
    input: SingleQubitInputInfo | None
    output: SingleQubitOutputInfo | None
    reusable: bool


class IOInfo:
    declaration_to_id: dict["str", list[int]]
    id_to_info: dict[int, SingleQubitIOInfo]

    def __init__(self) -> None:
        self.declaration_to_id = {}
        self.id_to_info = {}

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, IOInfo):
            return False
        return (
            self.declaration_to_id == value.declaration_to_id
            and self.id_to_info == value.id_to_info
        )
