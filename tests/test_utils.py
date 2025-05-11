from app.utils import duplicates


def test_duplicates() -> None:
    assert duplicates([]) == set()
    assert duplicates([1]) == set()
    assert duplicates([1, 2, 3]) == set()
    assert duplicates([2, 2, 3]) == {2}
    assert duplicates([2, 2, 2]) == {2}
    assert duplicates([1, 2, 2, 3, 4, 4]) == {2, 4}
    assert duplicates([1, 2, 2, 3, 4, 4]) == {4, 2}
