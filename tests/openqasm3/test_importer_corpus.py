"""Compare Qiskit's OpenQASM 3 importer against the universal exporter on a corpus.

Qiskit's OpenQASM 3 importer (``qiskit.qasm3.loads``, backed by
``qiskit_qasm3_import``) accepts only a subset of OpenQASM 3. The universal
exporter (``UniversalTranspiler`` with ``QiskitProvider``) builds Qiskit code
from the same OpenQASM 3 AST and covers the whole corpus, including the
constructs the importer rejects.

The corpus lives in ``tests/openqasm3/corpus``. The exporter validity bar
mirrors ``_transpile_qiskit`` in ``test_qiskit_transpiler.py``: the generated
code must compile as Python and must not contain ``TODO:`` or ``UNKNOWN_``
markers.
"""

from pathlib import Path

import pytest
import qiskit.qasm3
from openqasm3.parser import parse

from app.openqasm3.qiskit_provider import QiskitProvider
from app.openqasm3.universal_transpiler import UniversalTranspiler

CORPUS_DIR = Path(__file__).parent / "corpus"

# Accept/reject split of Qiskit's OpenQASM 3 importer, verified live against
# qiskit.qasm3.loads. Keyed by the corpus slug (filename without the NN_ prefix
# and the .qasm suffix).
IMPORTER_ACCEPTS = frozenset(
    {
        "if_simple",
        "for_simple",
        "while_simple",
        "alias",
        "float_input",
        "angle_input",
        "alias_concat",
        "annotations",
    }
)
IMPORTER_REJECTS = frozenset(
    {
        "compound_bool",
        "uint_input",
        "uint_output",
        "internal_classical_var",
        "bool_var",
    }
)


def _corpus_files() -> list[Path]:
    files = sorted(CORPUS_DIR.glob("*.qasm"))
    assert files, f"no corpus files found in {CORPUS_DIR}"
    return files


def _slug(path: Path) -> str:
    # ``00_if_simple.qasm`` -> ``if_simple``.
    return path.stem.split("_", 1)[1]


CORPUS_CASES = [pytest.param(path, id=path.stem) for path in _corpus_files()]


@pytest.mark.parametrize("path", CORPUS_CASES)
def test_exporter_produces_valid_qiskit_code(path: Path) -> None:
    """The exporter produces valid Qiskit code for every corpus case."""
    code = UniversalTranspiler(QiskitProvider()).visit_Program(
        parse(path.read_text(encoding="utf-8"))
    )
    compile(code, "<generated-qiskit>", "exec")
    assert "TODO:" not in code
    assert "UNKNOWN_" not in code


@pytest.mark.parametrize("path", CORPUS_CASES)
def test_importer_accept_reject_split(path: Path) -> None:
    """qiskit.qasm3.loads accepts the supported corpus cases and rejects the rest."""
    source = path.read_text(encoding="utf-8")
    slug = _slug(path)
    if slug in IMPORTER_ACCEPTS:
        assert isinstance(qiskit.qasm3.loads(source), qiskit.QuantumCircuit)
    else:
        assert slug in IMPORTER_REJECTS, f"unclassified corpus case: {slug}"
        with pytest.raises(qiskit.qasm3.QASM3ImporterError):
            qiskit.qasm3.loads(source)
