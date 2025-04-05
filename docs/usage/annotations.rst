Annotations
===========

A developer can create mappings between a concrete implementation (openqasm) and a program modeled in the `frontend <https://github.com/LEQO-Framework/low-code-modeler>`_ by using various openqasm3 annotations.

Annotations can be emulated in openqasm2 by using special comments.

.. warning::
    The `whole line <https://openqasm.com/language/directives.html#annotations#:~:text=continue%20to%20the%20end%20of%20the%20line>`_ will be interpreted like an annotation.
    Therefore you cannot use inline-comments on annotations!

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

The backend actively ensures that input memory is initialized.
All other qubits still have to be assumed to be in an undefined state (See `OpenQasm Specification <https://openqasm.com/language/types.html#qubits#:~:text=Qubits%20are%20initially%20in%20an%20undefined%20state>`_ and :ref:`reusable-qubit-annotation`).

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
    The identifier is insignificant and will be ignored.

.. _reusable-qubit-annotation:

Ancilla Qubits
--------------

If the programmer manually resets a qubit they can mark it as reusable.
To do so, one can declare an alias to the reusable qubits.

* Reusable qubits may not contain output qubits
* Reusable annotated aliases may be declared anywhere in code
* Reusable annotated aliases may be used like any other alias
* Reusable annotations may only appear above a :class:`~openqasm3.ast.AliasStatement` pointing to qubits
* Reusable annotations may only appear once per statement
* Reusable annotations guarantee that the backend is free to reuse the qubit (i.e. it is not entangled and reset to \|0⟩)

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
    The identifier is insignificant and will be ignored.
