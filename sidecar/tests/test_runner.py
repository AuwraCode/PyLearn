from __future__ import annotations

from tutor_sidecar.services.runner import find_python, run_tests

PY = find_python() or "python3"

ADD_TESTS = [
    {"call": "add(1, 2)", "expected": "3"},
    {"call": "add(-1, 1)", "expected": "0"},
]


def test_all_tests_pass() -> None:
    outcome = run_tests(PY, "def add(a, b):\n    return a + b", ADD_TESTS)
    assert outcome.passed
    assert not outcome.timed_out
    assert outcome.setup_error is None
    assert [entry["passed"] for entry in outcome.tests] == [True, True]
    assert outcome.duration_ms >= 0


def test_wrong_result_reports_expected_and_got() -> None:
    outcome = run_tests(PY, "def add(a, b):\n    return a - b", ADD_TESTS)
    assert not outcome.passed
    first = outcome.tests[0]
    assert first["passed"] is False
    assert first["expected"] == "3"
    assert first["got"] == "-1"


def test_exception_in_test_is_captured_per_test() -> None:
    outcome = run_tests(PY, "def add(a, b):\n    return a / 0", ADD_TESTS)
    assert not outcome.passed
    assert "ZeroDivisionError" in (outcome.tests[0]["error"] or "")


def test_syntax_error_lands_in_setup_error() -> None:
    outcome = run_tests(PY, "def add(:", ADD_TESTS)
    assert not outcome.passed
    assert outcome.setup_error is not None
    assert "SyntaxError" in outcome.setup_error
    assert outcome.tests == []


def test_infinite_loop_times_out() -> None:
    outcome = run_tests(PY, "while True:\n    pass", ADD_TESTS, timeout_s=0.5)
    assert outcome.timed_out
    assert not outcome.passed
    assert outcome.duration_ms >= 500


def test_user_prints_do_not_break_protocol() -> None:
    code = 'print("debuguję!")\ndef add(a, b):\n    return a + b'
    outcome = run_tests(PY, code, ADD_TESTS)
    assert outcome.passed
    assert "debuguję!" in outcome.stdout


def test_huge_output_is_truncated() -> None:
    code = 'print("x" * 100_000)\ndef add(a, b):\n    return a + b'
    outcome = run_tests(PY, code, ADD_TESTS, output_limit=1000)
    assert outcome.passed
    assert outcome.stdout.endswith("… (wyjście obcięte)")
    assert len(outcome.stdout) < 1100


def test_comparison_by_value_not_repr_formatting() -> None:
    # expected zapisane w stylu JSON (podwójne cudzysłowy) vs repr Pythona —
    # porównanie wartości przez ast.literal_eval musi to pogodzić.
    tests = [{"call": "words()", "expected": '["a", "b"]'}]
    outcome = run_tests(PY, "def words():\n    return ['a', 'b']", tests)
    assert outcome.passed


def test_dict_comparison_ignores_key_order() -> None:
    tests = [{"call": "make()", "expected": "{'a': 1, 'b': 2}"}]
    outcome = run_tests(PY, "def make():\n    return {'b': 2, 'a': 1}", tests)
    assert outcome.passed


def test_input_call_fails_fast_instead_of_hanging() -> None:
    outcome = run_tests(PY, 'name = input("kto? ")', ADD_TESTS)
    assert not outcome.passed
    assert not outcome.timed_out  # stdin=DEVNULL → natychmiastowy EOFError
    assert "EOFError" in (outcome.setup_error or "")
