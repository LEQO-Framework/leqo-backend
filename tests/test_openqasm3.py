import openqasm3.spec


def test_supported_versions():
    assert openqasm3.spec.supported_versions == ["3.0", "3.1"]
