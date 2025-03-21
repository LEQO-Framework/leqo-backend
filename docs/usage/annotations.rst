Annotations
===========

A developer can create mappings between a concrete implementation (openqasm) and a program modelled in the frontend by using various openqasm3 annotations.

Annotations can be emulated in openqasm2 by using special comments.

Input
-----

One input is defined as a single :class:`~openqasm3.ast.QubitDeclaration` with a single `@leqo.input` annotation.

* Inputs can be of arbitrary size
* Inputs need to be defined as contiguous memory
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

    // Single qubit
    @leqo.input <<InputIndex>>
    qubit someName;

.. note::
    The input might be split into separate non-contiguous memory blocks by the processor.

Output
------

One output is defines as a single :class:`~openqasm3.ast.AliasStatement` with a single `@leqo.output` annotation.

* Outputs may be concatenated from multiple non-contiguous blocks of memory.
* Output indices must be selected from a contiguous range of integers starting at `0`
    No skips, no duplicates
* Outputs may be declared anywhere in code
* Output annotations may only appear above a :class:`~openqasm3.ast.AliasStatement` pointing to qubits
* Output annotations may only appear once per statement

.. code-block:: openqasm3
    :linenos:

    @leqo.output <<OutputIndex>>
    let someOutput = <<Expression>>;

    // Example
    @leqo.output 0
    let output1 = a[1:2:3] ++ b[{1,2,3}];

Reusable Qubits
-----------------

If the programmer manually resets a qubit they can mark it as reusable.
To do so, one can declare an alias to the reusable qubits.

* Reusable annotations may only appear above a :class:`~openqasm3.ast.AliasStatement` pointing to qubits
* Reusable annotations may only appear once per statement

.. code-block:: openqasm3
    :linenos:

    @leqo.reusable
    let reusable1 = <<Expression>>;

    // Example
    @leqo.reusable
    let reusable1 = a[0];
