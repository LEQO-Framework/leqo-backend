Annotations
===========

A developer can create mappings between a concrete implementation (openqasm) and a program modeled in the `frontend <https://github.com/LEQO-Framework/low-code-modeler>`_ by using various openqasm3 annotations.

Annotations can be emulated in openqasm2 by using special comments.

.. warning::
    The `whole line <https://openqasm.com/language/directives.html#annotations#:~:text=continue%20to%20the%20end%20of%20the%20line>`_ will be interpreted like an annotation.
    Therefore you cannot use inline-comments on annotations!

.. _input-anker:

Input
-----

One input is defined as a single qubit register (:class:`~openqasm3.ast.QubitDeclaration`) with a single `@leqo.input` annotation.
The annotation specifies the index of the corresponding input.

* Inputs can be of arbitrary size (See :ref:`input-memory-layout`)
* Inputs have to be defined as contiguous memory
    One :class:`~openqasm3.ast.QubitDeclaration` corresponds to one input
* Input indices must be selected from a contiguous range of integers starting at `0`
   No skips, no duplicates
* Inputs may be declared anywhere in code
* Input annotations may only appear on a :class:`~openqasm3.ast.QubitDeclaration`
* Input annotations may only appear once per statement

.. code-block:: openqasm3
    :linenos:

    // Qubit array
    @leqo.input <<InputIndex>>
    qubit[<<length>>] someName;

.. code-block:: openqasm3
    :linenos:

    // Single qubit
    @leqo.input <<InputIndex>>
    qubit someName;

`<<InputIndex>>` is replaced with the index of an input (positive integer literal)

.. code-block:: openqasm3
    :linenos:

    // Example
    @leqo.input 0
    qubit someName;

.. _input-memory-layout:

Memory Layout
~~~~~~~~~~~~~

There is no explicit limit to the size (qubit count) of an input.
However, the number of physical qubits on a real device is limited.
See :ref:`reusable-qubit-annotation` for workarounds.

The annotated input size must match the input size of the corresponding node from the `visual model <https://github.com/LEQO-Framework/low-code-modeler>`_.
Inputs are expected to be **Little Endian**.

The backend actively ensures that input qubits are initialized.
All other qubits can be assumed to be `\|0⟩`.

.. note::
    The `specification <https://openqasm.com/language/types.html#qubits#:~:text=Qubits%20are%20initially%20in%20an%20undefined%20state>`_ allows implementors of openqasm3 to initialize qubits to an undefined state.
    However, in practice major implementations (e.g. IBM) initialize qubits to `\|0⟩`.

In the future, it is planned to allow to input less qubits than specified using the annotation.
In this case the backend would fill the lowest bytes with the actual input and ensure the upper bytes are initialized to zero:

    .. csv-table:: Example input register of size `7`
        :header: "0", "1", "2", "3", "4", "5", "6"

        "p[0]", "p[1]", "p[2]", "p[3]", "p[4]", "p[5]", "p[6]"
        "p[0]", "p[1]", "\|0⟩", "\|0⟩", "\|0⟩", "\|0⟩", "\|0⟩"

Output
------

One output is defined as a single alias (:class:`~openqasm3.ast.AliasStatement`) with a single `@leqo.output` annotation.
The annotation specifies the index of the corresponding output.

* One qubit may only be used in one output at most
* Outputs may be concatenated from multiple non-contiguous blocks of memory.
* Output indices must be selected from a contiguous range of integers starting at `0`
    No skips, no duplicates
* Outputs may be declared anywhere in code
* Outputs may be used like any other alias
* Output annotations may only appear above a :class:`~openqasm3.ast.AliasStatement` pointing to qubits
* Output annotations may only appear once per statement

.. code-block:: openqasm3
    :linenos:

    @leqo.output <<OutputIndex>>
    let someOutput = <<Expression>>;

`<<OutputIndex>>` is replaced with the index of an output (positive integer literal)

.. code-block:: openqasm3
    :linenos:

    // Example
    qubit[10] a;
    qubit[4] b;

    @leqo.output 0
    let output1 = a[1:2:3] ++ b[{1,2,3}];

.. note::
    Even if the ouput alias is not used in code, an alias must be defined to mark qubits as outputs.
    The identifier is insignificant.

Qubit Classification
--------------------
In LEQO’s OpenQASM snippet-based design, a set of semantic labels is introduced to characterize
how qubits are utilized and managed, enabling more effective reasoning about the qubit lifecycle
and the data flow between snippets.

.. list-table:: Ingoing Qubits
   :widths: 20 80
   :header-rows: 1

   * - Name
     - Description
   * - Linking Qubit
     - A qubit annotated with ``@leqo.input``.
       These qubits serve as the entry points for quantum states passed between snippets
       and may be in arbitrary or entangled states.
   * - Clean Ancilla
     - A qubit declared in the current snippet without any annotation.
       It is initialized to ``|0⟩`` and can serve as clean temporary workspace
       or be used to introduce a working qubit intended to pass information to other snippets as a Linking Qubit.
   * - Dirty Ancilla
     - A qubit used for temporary computation that may be entangled or hold an unknown state.
       Declared with ``@leqo.dirty``, it must not be measured
       and must be restored to its original state before the snippet ends.

.. list-table:: Outgoing Qubits
   :widths: 20 80
   :header-rows: 1

   * - Name
     - Description
   * - Linking Qubit
     - A qubit annotated with ``@leqo.output`` .
       These qubits serve as the exit points for quantum states passed between snippets
       and may be in arbitrary or entangled states.
   * - Reusable Ancilla
     - A qubit explicitly reset to ``|0⟩`` by the user and annotated with ``@leqo.reusable``.
       It may originate as a clean ancilla or linking qubit and must be disentangled from all other qubits before reuse.
       Reusable ancillae are considered clean ancillae in future snippets.
   * - Uncomputable Ancilla
     - A qubit annotated with ``@leqo.reusable`` within a ``@leqo.uncompute`` block.
       These qubits are only uncomputed and returned to clean ancillae when the compiler deems it necessary,
       allowing the code as a whole to be optimised.
   * - Entangled Ancilla
     - A qubit that is neither annotated with ``@leqo.output`` nor with ``@leqo.reusable`` within the snippet.
       It may be in a non-zero or entangled state and cannot safely be reused without restrictions.
       Entangled ancillae are considered dirty ancillae in future snippets.

.. _reusable-qubit-annotation:

Ancilla Qubits
--------------

If the programmer manually resets a qubit they can mark it as reusable.
To do so, one can declare an alias to the reusable qubits.

* Reusable qubits may not be marked as output
* Reusable annotated aliases may be declared anywhere in code
* Reusable annotated aliases may be used like any other alias
* Reusable annotations may only appear above a :class:`~openqasm3.ast.AliasStatement` pointing to qubits
* Reusable annotations may only appear once per statement
* Reusable annotations mark qubits that are no longer entangled and reset to \|0⟩
    This actions has to be manually implemented by the user and guarantees that the backend is free to reuse the qubit

.. code-block:: openqasm3
    :linenos:

    @leqo.reusable
    let reusable1 = <<Expression>>;

.. code-block:: openqasm3
    :linenos:

    // Example
    @leqo.reusable
    let reusable1 = a[0];

.. note::
    Even if the reusable alias is not used in code, an alias must be defined to mark qubits as reusable.
    The identifier is insignificant.

Dirty Ancilla Qubits
--------------------

If qubits are used in a program and are neither marked as output nor reusable, they are considered dirty ancilla qubits.
These qubits may be in an arbitrary state, including entanglement with other qubits, and require the explicit `@leqo.dirty` annotation to indicate their intended use in another snippet.
A dirty ancilla may be promoted to a reusable ancilla via an associated uncomputation block.

To use dirty ancillae within a snippet, the programmer must explicitly opt in by annotating the qubit definition with `@leqo.dirty`.

* The `@leqo.dirty` annotation follows the same implementation rules as input definitions, but omits indexing, as defined in :ref:`input definition <input-anker>`

.. warning::
    The state of a dirty ancilla qubit can be altered temporarily but must be restored at the end of a snippet.
    Therefore measuring a dirty qubit is not permitted.

.. code-block:: openqasm3
    :linenos:

    // Single dirty ancilla
    @leqo.dirty
    qubit singleDirtyAncilla;

.. code-block:: openqasm3
    :linenos:

    // Dirty ancilla array
    @leqo.dirty
    qubit[<<length>>] dirtyAncillaArray;

Uncomputation
-------------
When dirty ancilla qubits can be uncomputed, the programmer may provide an explicit uncomputation block to reverse their effects.
This is done using the `@leqo.uncompute` annotation, which defines a scoped region that is disabled by default via an `if (false)` statement.
The compiler may override this value to `true` if uncomputation of the associated dirty ancillae is required.

* The `@leqo.uncompute` annotation must appear directly above an `if (false)` statement with a block body that must not be followed by an `else` statement
* `@leqo.uncompute` annotations may appear multiple times in a program, each time referring to different uncomputation logic
* Nested `@leqo.uncompute` if-blocks are not allowed
* A `@leqo.uncompute` if-block must be declared at global scope
* The `@leqo.uncompute` block must reverse all transformations on the associated ancillae, removing entanglement and restoring each to the ``|0⟩`` state
* `@leqo.uncompute` blocks only operate on existing variables, qubits or selfdeclared aliases
* A `@leqo.uncompute` if-block must declare the uncomputed ancillae as reusable qubits by using the corresponding `@leqo.reusable` annotation

.. warning::
    Qubits previously annotated with `@leqo.dirty` must not be uncomputed

.. note::
    Not all operations are reversible; in such cases, the qubit should not be reused.

.. code-block:: openqasm3
    :linenos:

    @leqo.uncompute
    if (false) {
        // some uncompute operation

        @leqo.reusable
        let reusable1 = dirtyAncilla1
    }

QASM 2
~~~~~~
An uncompute block is marked explicitly, as shown below:

.. code-block:: openqasm2
    :linenos:

    // @leqo.uncompute start
    // someUncomputeOperation
    //
    // @leqo.reusable
    // let reusable1 = dirtyAncilla1
    // @leqo.uncompute end

.. note::
    * Every line of the uncompute block must start with ``//``
    * A uncompute block must start with ``// @leqo.uncompute start`` and end with ``// @leqo.uncompute end``