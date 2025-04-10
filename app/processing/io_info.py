"""Dataclasses for various types of io info."""

from abc import ABC
from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from openqasm3.ast import BoolType, ClassicalType, FloatType, IntType, UintType


@dataclass()
class RegSingleInputInfo:
    """Store a single input info for a reg-stored type.

    :param input_index: index of the input
    :param reg_position: position in the register
    """

    input_index: int
    reg_position: int


@dataclass()
class RegSingleOutputInfo:
    """Store a single output info for a reg-stored type.

    :param output_index: index of the output
    :param reg_position: position in the register
    """

    output_index: int
    reg_position: int


@dataclass()
class RegAnnotationInfo:
    """Store input and output for a single reg-stored type."""

    input: RegSingleInputInfo | None = None
    output: RegSingleOutputInfo | None = None


AT = TypeVar("AT", bound=RegAnnotationInfo)


@dataclass()
class RegIOInfo(Generic[AT], ABC):
    """Abstract class for IO info of types that are stored in registers.

    For this purpose, every instance (not register) is given an id, based on declaration order.
    Then id_to_info maps these id's to the corresponding :class:`app.processing.graph.RegAnnotationInfo`.

    These types are currently:
    - Qubits
    - Bits
    """

    declaration_to_ids: dict[str, list[int]]
    id_to_info: dict[int, AT]
    input_to_ids: dict[int, list[int]]
    output_to_ids: dict[int, list[int]]

    def __init__(
        self,
        declaration_to_ids: dict[str, list[int]] | None = None,
        id_to_info: dict[int, AT] | None = None,
        input_to_ids: dict[int, list[int]] | None = None,
        output_to_ids: dict[int, list[int]] | None = None,
    ) -> None:
        """Construct RegIOInfo.

        :param declaration_to_ids: Maps declared instance names to list of IDs.
        :param id_to_info: Maps IDs to their corresponding info objects.
        :param input_to_ids: Maps input indexes to their corresponding IDs.
        :param output_to_ids: Maps output indexes to their corresponding IDs.
        """
        self.declaration_to_ids = declaration_to_ids or {}
        self.id_to_info = id_to_info or {}
        self.input_to_ids = input_to_ids or {}
        self.output_to_ids = output_to_ids or {}


BitIOInfo = RegIOInfo[RegAnnotationInfo]


@dataclass()
class QubitAnnotationInfo(RegAnnotationInfo):
    """Store input, output and reusable info for a single qubit."""

    reusable: bool = False
    dirty: bool = False


@dataclass()
class QubitIOInfo(RegIOInfo[QubitAnnotationInfo]):
    """Store input, output, dirty, reusable and uncompute info for qubits in a qasm-snippet."""

    id_to_info: dict[int, QubitAnnotationInfo]
    required_ancillas: list[int]
    dirty_ancillas: list[int]
    reusable_ancillas: list[int]
    reusable_after_uncompute: list[int]  # TODO: not implemented
    returned_dirty_ancillas: list[int]

    def __init__(  # noqa: PLR0913
        self,
        declaration_to_ids: dict[str, list[int]] | None = None,
        id_to_info: dict[int, QubitAnnotationInfo] | None = None,
        input_to_ids: dict[int, list[int]] | None = None,
        output_to_ids: dict[int, list[int]] | None = None,
        required_ancillas: list[int] | None = None,
        dirty_ancillas: list[int] | None = None,
        reusable_ancillas: list[int] | None = None,
        reusable_after_uncompute: list[int] | None = None,
        returned_dirty_ancillas: list[int] | None = None,
    ) -> None:
        """Construct QubitIOInfo.

        :param declaration_to_ids: Maps declared qubit names to list of IDs.
        :param id_to_info: Maps IDs to their corresponding info objects.
        :param input_to_ids: Maps input indexes to their corresponding IDs.
        :param output_to_ids: Maps output indexes to their corresponding IDs.
        :param required_ancillas: Id list of required non-dirty ancillas.
        :param dirty_ancillas: Id list of required (possible) dirty ancillas.
        :param reusable_ancillas: Id list of reusable ancillas.
        :param reusable_after_uncompute: Id list of additional reusable ancillas after uncompute.
        :param returned_dirty_ancillas: Id list of ancillas that are returned dirty in any case.
        """
        super().__init__(declaration_to_ids, id_to_info, input_to_ids, output_to_ids)
        self.required_ancillas = required_ancillas or []
        self.dirty_ancillas = dirty_ancillas or []
        self.reusable_ancillas = reusable_ancillas or []
        self.reusable_after_uncompute = reusable_after_uncompute or []
        self.returned_dirty_ancillas = returned_dirty_ancillas or []


@dataclass()
class SizedSingleInputInfo:
    """Store a single input info for a sized type.

    :param input_index: index of the input
    :param size: the size of the instance
    """

    input_index: int
    size: int


@dataclass()
class SizedSingleOutputInfo:
    """Store a single output info for a sized type.

    :param output: index of the input
    :param size: the size of the instance
    """

    output_index: int
    size: int


@dataclass()
class SizedAnnotationInfo:
    """Store input and output for a single sized type."""

    input: SizedSingleInputInfo | None = None
    output: SizedSingleOutputInfo | None = None


@dataclass()
class SizedIOInfo(ABC):
    """Abstract class for IO info of sized types.

    These types are currently:
    - Integers
    - Unsigned Integers
    - Floats
    - Booleans (with fixed size 1)
    """

    declaration_to_id: dict[str, int]
    id_to_info: dict[int, SizedAnnotationInfo]
    input_to_id: dict[int, int]
    output_to_id: dict[int, int]
    instance_type: ClassVar[type[ClassicalType] | None]

    def __init__(
        self,
        declaration_to_id: dict[str, int] | None = None,
        id_to_info: dict[int, SizedAnnotationInfo] | None = None,
        input_to_id: dict[int, int] | None = None,
        output_to_id: dict[int, int] | None = None,
    ) -> None:
        """Construct SizedAnnotationInfo.

        :param declaration_to_id: Maps declared instance names to ID.
        :param id_to_info: Maps IDs to their corresponding info objects.
        :param input_to_ids: Maps input indexes to their corresponding ID.
        :param output_to_ids: Maps output indexes to their corresponding ID.
        """
        self.declaration_to_id = declaration_to_id or {}
        self.id_to_info = id_to_info or {}
        self.input_to_id = input_to_id or {}
        self.output_to_id = output_to_id or {}


class IntIOInfo(SizedIOInfo):
    instance_type = IntType


class UIntIOInfo(SizedIOInfo):
    instance_type = UintType


class FloatIOInfo(SizedIOInfo):
    instance_type = FloatType


class BoolIOInfo(SizedIOInfo):
    instance_type = BoolType


@dataclass()
class CombinedIOInfo:
    qubit: QubitIOInfo
    bit: BitIOInfo
    int: IntIOInfo
    uint: UIntIOInfo
    float: FloatIOInfo
    bool: BoolIOInfo

    def __init__(
        self,
        qubit: QubitIOInfo | None = None,
        bit: BitIOInfo | None = None,
        int: IntIOInfo | None = None,
        uint: UIntIOInfo | None = None,
        float: FloatIOInfo | None = None,
        bool: BoolIOInfo | None = None,
    ) -> None:
        self.qubit = qubit or QubitIOInfo()
        self.bit = bit or BitIOInfo()
        self.int = int or IntIOInfo()
        self.uint = uint or UIntIOInfo()
        self.float = float or FloatIOInfo()
        self.bool = bool or BoolIOInfo()
