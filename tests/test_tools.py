from __future__ import annotations

import pytest

from sirius.files.service import FileService
from sirius.utils.calculator import calculate
from sirius.utils.python_runner import run_python

# ── calculator ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("2 ** 10", 1024),
        ("sqrt(144)", 12),
        ("round(pi, 2)", 3.14),
        ("-5 + abs(-3)", -2),
        ("10 % 3", 1),
    ],
)
def test_calculate(expression, expected):
    assert calculate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    "malicious",
    [
        "__import__('os').system('dir')",
        "open('x').read()",
        "'a' * 10",
        "[1,2,3]",
        "exec('print(1)')",
    ],
)
def test_calculate_rejects_non_arithmetic(malicious):
    with pytest.raises((ValueError, SyntaxError)):
        calculate(malicious)


# ── python runner ────────────────────────────────────────────


def test_run_python_output(tmp_path):
    assert run_python("print(sum(range(101)))", tmp_path) == "5050"


def test_run_python_error_reported(tmp_path):
    assert "ZeroDivisionError" in run_python("print(1/0)", tmp_path)


def test_run_python_timeout(tmp_path):
    result = run_python("while True: pass", tmp_path, timeout=2)
    assert "exceeded" in result


def test_run_python_can_read_workspace_files(tmp_path):
    (tmp_path / "data.txt").write_text("hello from file")
    assert run_python("print(open('data.txt').read())", tmp_path) == "hello from file"


# ── file service ─────────────────────────────────────────────


def test_file_save_list_preview_csv(settings):
    files = FileService(settings)
    files.save("u1", "vendas.csv", b"produto,total\nleite,10\npao,5\n")

    listed = files.list_files("u1")
    assert [f["name"] for f in listed] == ["vendas.csv"]

    preview = files.preview("u1", "vendas.csv")
    assert "produto | total" in preview
    assert "leite | 10" in preview


def test_file_preview_missing(settings):
    files = FileService(settings)
    with pytest.raises(FileNotFoundError):
        files.preview("u1", "nope.csv")


def test_file_names_are_sanitized(settings):
    files = FileService(settings)
    path = files.save("u1", "../../evil.csv", b"x")
    assert path.parent == files.workdir("u1")


def test_files_scoped_per_user(settings):
    files = FileService(settings)
    files.save("u1", "a.csv", b"x")
    assert files.list_files("u2") == []
