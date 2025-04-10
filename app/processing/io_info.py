"""Dataclasses for various types of io info."""

from abc import ABC
from dataclasses import dataclass, field
from typing import ClassVar, Generic, TypeVar

from openqasm3.ast import BoolType, ClassicalType, FloatType, IntType


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

    :param declaration_to_ids: Maps declared instance names to list of IDs.
    :param id_to_info: Maps IDs to their corresponding info objects.
    :param input_to_ids: Maps input indexes to their corresponding IDs.
    :param output_to_ids: Maps output indexes to their corresponding IDs.
    """

    declaration_to_ids: dict[str, list[int]] = field(default_factory=dict)
    id_to_info: dict[int, AT] = field(default_factory=dict)
    input_to_ids: dict[int, list[int]] = field(default_factory=dict)
    output_to_ids: dict[int, list[int]] = field(default_factory=dict)


BitIOInfo = RegIOInfo[RegAnnotationInfo]


@dataclass()
class QubitAnnotationInfo(RegAnnotationInfo):
    """Store input, output and reusable info for a single qubit."""

    reusable: bool = False
    dirty: bool = False


@dataclass()
class QubitIOInfo(RegIOInfo[QubitAnnotationInfo]):
    """Store input, output, dirty and reusable info for qubits in a qasm-snippet.

    For this purpose, every qubit (not qubit-reg) is given an id, based on declaration order.
    Then id_to_info maps these id's to the corresponding :class:`app.processing.graph.QubitAnnotationInfo`.
    Warning: uncompute parse not inplemented yet.

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

    required_ancillas: list[int] = field(default_factory=list)
    dirty_ancillas: list[int] = field(default_factory=list)
    reusable_ancillas: list[int] = field(default_factory=list)
    reusable_after_uncompute: list[int] = field(default_factory=list)
    returned_dirty_ancillas: list[int] = field(default_factory=list)


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

    declaration_to_id: dict[str, int] = field(default_factory=dict)
    id_to_info: dict[int, SizedAnnotationInfo] = field(default_factory=dict)
    input_to_id: dict[int, int] = field(default_factory=dict)
    output_to_id: dict[int, int] = field(default_factory=dict)
    instance_type: ClassVar[type[ClassicalType] | None] = None


class IntIOInfo(SizedIOInfo):
    instance_type = IntType


class FloatIOInfo(SizedIOInfo):
    instance_type = FloatType


class BoolIOInfo(SizedIOInfo):
    instance_type = BoolType


@dataclass()
class CombinedIOInfo:
    qubit: QubitIOInfo = field(default_factory=QubitIOInfo)
    bit: BitIOInfo = field(default_factory=BitIOInfo)
    int: IntIOInfo = field(default_factory=IntIOInfo)
    float: FloatIOInfo = field(default_factory=FloatIOInfo)
    bool: BoolIOInfo = field(default_factory=BoolIOInfo)
