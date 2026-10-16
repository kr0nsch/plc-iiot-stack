"""stlayout.py (и другие скрипты CODESYS) должны работать в IronPython 2.7 без изменений.

Интерпретатора 2.7 в окружении нет, поэтому проверяется синтаксис через ast Python 3:
нет конструкций, которых нет в 2.7, и нет модулей и имён только из Python 3.
"""

from __future__ import annotations

import ast
import re
import tokenize
from pathlib import Path

import pytest

from conftest import REPO_ROOT

CODESYS_DIR = REPO_ROOT / "tools" / "codesys"
SCRIPTS = sorted(CODESYS_DIR.glob("*.py"))

PY3_ONLY_MODULES = {
    "pathlib",
    "dataclasses",
    "typing",
    "enum",
    "asyncio",
    "concurrent",
    "tomllib",
    "secrets",
    "statistics",
    "zoneinfo",
    "graphlib",
}
PY3_ONLY_NAMES = {
    "FileNotFoundError",
    "FileExistsError",
    "PermissionError",
    "NotADirectoryError",
    "IsADirectoryError",
    "ModuleNotFoundError",
    "RecursionError",
    "TimeoutError",
    "ConnectionError",
    "nonlocal",
    "breakpoint",
}
PY3_ONLY_ATTRS = {"casefold", "fullmatch", "isascii", "removeprefix", "removesuffix", "isidentifier"}


class Py3Finder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.problems: list[str] = []
        self._mypy_guard = 0

    def bad(self, node: ast.AST, what: str) -> None:
        self.problems.append(f"строка {getattr(node, 'lineno', '?')}: {what}")

    def visit_If(self, node: ast.If) -> None:
        # if MYPY: импорт typing только для mypy — в IronPython не выполняется
        if isinstance(node.test, ast.Name) and node.test.id in ("MYPY", "TYPE_CHECKING"):
            self._mypy_guard += 1
            for child in node.body:
                self.visit(child)
            self._mypy_guard -= 1
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self.bad(node, "f-строка")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.bad(node, "аннотация переменной")

    def _check_args(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        args = node.args
        if args.kwonlyargs:
            self.bad(node, "аргументы только по имени (после *)")
        if args.posonlyargs:
            self.bad(node, "аргументы только по позиции (/)")
        for arg in [*args.args, *args.kwonlyargs]:
            if arg.annotation is not None:
                self.bad(node, f"аннотация аргумента {arg.arg}")
        for extra in (args.vararg, args.kwarg):
            if extra is not None and extra.annotation is not None:
                self.bad(node, f"аннотация аргумента {extra.arg}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_args(node)
        if node.returns is not None:
            self.bad(node, "аннотация результата")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.bad(node, "async def")

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._check_args(node)
        self.generic_visit(node)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.bad(node, "nonlocal")

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self.bad(node, "yield from")

    def visit_Await(self, node: ast.Await) -> None:
        self.bad(node, "await")

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.bad(node, "оператор :=")

    def visit_Raise(self, node: ast.Raise) -> None:
        if node.cause is not None:
            self.bad(node, "raise ... from")
        self.generic_visit(node)

    def visit_Starred(self, node: ast.Starred) -> None:
        self.bad(node, "распаковка *x вне вызова функции")

    def visit_Call(self, node: ast.Call) -> None:
        # f(*args) в 2.7 допустим: проверяем аргументы, но не сам Starred
        self.visit(node.func)
        starred = [a for a in node.args if isinstance(a, ast.Starred)]
        if len(starred) > 1:
            self.bad(node, "несколько *args в вызове")
        if starred and node.args.index(starred[0]) != len(node.args) - 1:
            self.bad(node, "позиционный аргумент после *args")
        for arg in node.args:
            self.visit(arg.value if isinstance(arg, ast.Starred) else arg)
        if sum(1 for k in node.keywords if k.arg is None) > 1:
            self.bad(node, "несколько **kwargs в вызове")
        for keyword in node.keywords:
            if keyword.arg == "exist_ok":
                self.bad(node, "os.makedirs(exist_ok=...) есть только в Python 3")
            self.visit(keyword.value)

    def visit_Dict(self, node: ast.Dict) -> None:
        if any(key is None for key in node.keys):
            self.bad(node, "распаковка ** в литерале словаря")
        self.generic_visit(node)

    def visit_MatMult(self, node: ast.MatMult) -> None:
        self.bad(node, "оператор @")

    def visit_Match(self, node: ast.Match) -> None:
        self.bad(node, "match")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not node.bases:
            self.bad(node, f"class {node.name} без (object): в 2.7 это класс старого стиля")
        if node.keywords:
            self.bad(node, "ключевые аргументы в объявлении класса (metaclass=...)")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".")[0] in PY3_ONLY_MODULES and not self._mypy_guard:
                self.bad(node, f"модуль только Python 3: {alias.name}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".")[0]
        if module in PY3_ONLY_MODULES and not self._mypy_guard:
            self.bad(node, f"модуль только Python 3: {node.module}")

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in PY3_ONLY_NAMES:
            self.bad(node, f"имя только Python 3: {node.id}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in PY3_ONLY_ATTRS:
            self.bad(node, f"метод только Python 3: .{node.attr}")
        if node.attr == "__init__" or not isinstance(node.value, ast.Call):
            self.generic_visit(node)
            return
        call = node.value
        if isinstance(call.func, ast.Name) and call.func.id == "super" and not call.args:
            self.bad(node, "super() без аргументов")
        self.generic_visit(node)


def problems_of(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    finder = Py3Finder()
    finder.visit(tree)
    problems = list(finder.problems)
    future = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "__future__"
        for alias in node.names
    }
    for name in ("absolute_import", "print_function", "unicode_literals"):
        if name not in future:
            problems.append(f"нет from __future__ import {name}")
    if "annotations" in future:
        problems.append("from __future__ import annotations нет в Python 2.7")
    # Запятая после *args/**kwargs в определении или вызове — SyntaxError в 2.7
    for match in re.finditer(r"\*\*?\s*[A-Za-z_][A-Za-z0-9_.]*\s*,\s*\)", source):
        problems.append(f"запятая после *args/**kwargs: {match.group(0)!r}")
    # Префиксы строк, которых нет в 2.7: f'', rb'' (в 2.7 только br'')
    with path.open("rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type == tokenize.STRING and re.match(r"(?i)(rb|f|fr|rf)['\"]", tok.string):
                problems.append(f"строка {tok.start[0]}: префикс строки {tok.string[:3]!r} нет в 2.7")
    return problems


@pytest.mark.parametrize("path", SCRIPTS, ids=[p.name for p in SCRIPTS])
def test_codesys_script_is_py27_compatible(path: Path) -> None:
    assert problems_of(path) == []


def test_stlayout_is_checked() -> None:
    assert CODESYS_DIR / "stlayout.py" in SCRIPTS


def test_checker_detects_py3_constructs(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from __future__ import absolute_import, print_function, unicode_literals\n"
        "import pathlib\n"
        "def f(a: int, *rest, key=1) -> None:\n"
        "    x: int = 1\n"
        "    print(f'{a}')\n"
        "    raise ValueError() from None\n"
        "class C:\n"
        "    def m(self):\n"
        "        return super().m()\n"
        "first, *other = [1, 2]\n"
        "g(*other,)\n",
        encoding="utf-8",
    )
    text = "\n".join(problems_of(bad))
    for expected in (
        "pathlib",
        "аннотация аргумента a",
        "аннотация результата",
        "аннотация переменной",
        "f-строка",
        "raise ... from",
        "class C",
        "super()",
        "распаковка *x",
        "запятая после *args",
    ):
        assert expected in text
