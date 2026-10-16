"""Совместимые замены текста ST для вариантов сборки rusty и iec-checker.

Каждый проход — функция «текст -> текст» на токенах stlayout. Проходы сохраняют
число строк фрагмента (удалённые переводы строк возвращаются в конец замены), поэтому
карта строк build/assembled/sourcemap.json остаётся точной. Таблицы правил — в
tools/README.md («Варианты сборки»).
"""

from __future__ import annotations

import itertools
import os
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "codesys"))
import stlayout as L

Token = L.Token

# Имена типов CODESYS Standard, сигнатура которых отличается от стандартной библиотеки RuSTy.
# Для проверки RuSTy они заменяются на прокладки из tools/check/rusty_shims/codesys_standard.st.
RUSTY_TYPE_RENAMES = {"CTU": "CDS_CTU", "CTD": "CDS_CTD", "CTUD": "CDS_CTUD"}

ITF_HELPER_NAME = "__ItfIsSet"
ITF_HELPER = """(* Вспомогательная функция совместимости для проверки RuSTy (не для CODESYS):
   проверка, что интерфейсная переменная задана (itfX <> 0 в CODESYS). *)
FUNCTION __ItfIsSet : BOOL
VAR_INPUT
    pFat : POINTER TO LWORD;
END_VAR
__ItfIsSet := pFat^ <> 0;
END_FUNCTION
"""

_INT_TYPES = (
    "SINT",
    "INT",
    "DINT",
    "LINT",
    "USINT",
    "UINT",
    "UDINT",
    "ULINT",
    "BYTE",
    "WORD",
    "DWORD",
    "LWORD",
)
_ELEMENTARY_TYPES = frozenset(
    (
        *_INT_TYPES,
        "BOOL",
        "REAL",
        "LREAL",
        "T",
        "TIME",
        "LT",
        "LTIME",
        "D",
        "DATE",
        "LD",
        "LDATE",
        "DT",
        "DATE_AND_TIME",
        "LDT",
        "TOD",
        "TIME_OF_DAY",
        "LTOD",
        "STRING",
        "WSTRING",
    )
)
_BIT_STRING_TYPES = ("BYTE", "WORD", "DWORD", "LWORD")
_REAL_TYPES = ("REAL", "LREAL")
_DURATION_PREFIXES = ("T", "TIME", "LT", "LTIME")
_DATE_PREFIXES = ("D", "DATE", "LD", "LDATE", "DT", "DATE_AND_TIME", "LDT", "TOD", "TIME_OF_DAY", "LTOD")
_DURATION_UNITS = ("D", "H", "M", "S", "MS", "US", "NS")
_DURATION_PART_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)(MS|US|NS|D|H|M|S)", re.IGNORECASE)
# Ключевые слова разборщика iec_checker v0.4 (src/parser/lexer.mll, таблица keywords_table), которые в
# CODESYS ключевыми словами не являются и встречаются как имена переменных, свойств и методов. В варианте
# iec-checker такие идентификаторы получают суффикс '_' (последовательно во всём тексте). Ключевые слова,
# общие с CODESYS (PROGRAM, METHOD, RETAIN, CONSTANT, ...), и имена типов (LDATE, CHAR, ...) не переименовываются:
# в коде CODESYS они именами быть не могут или означают тип.
IEC_CHECKER_RESERVED = frozenset(
    (
        "PRIORITY",
        "INTERVAL",
        "SINGLE",
        "ON",
        "TASK",
        "RESOURCE",
        "END_RESOURCE",
        "WITH",
        "READ_ONLY",
        "READ_WRITE",
        "OVERLAP",
        "NULL",
        "REF",
        "CLASS",
        "END_CLASS",
        "OVERRIDE",
        "EQU",
    )
)
# Управляющие слова ST, которые лексер iec_checker v0.4 узнаёт только в верхнем регистре
_CASE_SENSITIVE_KEYWORDS = frozenset(
    (
        "IF",
        "THEN",
        "ELSIF",
        "ELSE",
        "END_IF",
        "CASE",
        "OF",
        "END_CASE",
        "FOR",
        "TO",
        "BY",
        "DO",
        "END_FOR",
        "WHILE",
        "END_WHILE",
        "REPEAT",
        "END_REPEAT",
        "UNTIL",
        "EXIT",
        "CONTINUE",
        "RETURN",
        "TRUE",
        "FALSE",
    )
)
# Заглушки понижения iec-checker: пустой оператор, составной индекс, операторы TIME() и LTIME()
NOP_CALL = "CDS__NOP();"
INDEX_FUNCTION = "CDS__IDX"
TIME_FUNCTION_PREFIX = "CDS__"
# Повторы прохода обращений к элементам массивов (вложенные обращения — по одному уровню за проход)
ELEMENT_ACCESS_PASSES = 4
# Верхняя граница массива, если её не удалось вычислить (широкий диапазон: проверка длины
# списка начальных значений OutOfBounds не даёт ложных находок)
DUMMY_ARRAY_SPAN = 32767
_ITF_NAME_RE = re.compile(r"itf[A-Z0-9_]")
# Токены, после которых начинается оператор
_STATEMENT_PRECEDERS = (
    "THEN",
    "ELSE",
    "DO",
    "REPEAT",
    "OF",
    "END_IF",
    "END_CASE",
    "END_FOR",
    "END_WHILE",
    "END_REPEAT",
)


@dataclass
class Context:
    """Сведения обо всём наборе объектов, нужные проходам."""

    gvl_names: set[str] = field(default_factory=set)  # имена GVL/PVL (нижний регистр)
    enum_values: dict[str, dict[str, int]] = field(default_factory=dict)
    gvl_int_constants: dict[str, dict[str, int]] = field(default_factory=dict)
    # целые константы VAR CONSTANT собираемого POU (задаёт сборка перед каждым объектом)
    local_int_constants: dict[str, int] = field(default_factory=dict)
    struct_members: dict[str, tuple[list[str], list[str]]] = field(default_factory=dict)
    strip_namespaces: list[str] = field(default_factory=list)
    used_itf_helper: bool = False

    @classmethod
    def from_objects(cls, objects: Iterable[L.StObject], strip_namespaces: Sequence[str] = ()) -> Context:
        ctx = cls(strip_namespaces=[ns.rstrip(".") for ns in strip_namespaces if ns.strip(".")])
        pending: list[tuple[str, list[str], str]] = []  # (GVL, имена, начальное значение)
        for obj in objects:
            if obj.kind in (L.KIND_GVL, L.KIND_PVL):
                ctx.gvl_names.add(obj.name.lower())
                ctx.gvl_int_constants[obj.name.lower()] = {}
                for block in L.parse_var_blocks(obj.decl):
                    if "CONSTANT" not in block.modifiers:
                        continue
                    for decl in block.decls:
                        if decl.init_text:
                            pending.append((obj.name.lower(), decl.name_list, decl.init_text))
            elif obj.kind == L.KIND_DUT:
                tdecl = L.parse_type_decl(obj.decl)
                if tdecl is None:
                    continue
                if tdecl.kind == "enum":
                    values: dict[str, int] = {}
                    current = -1
                    for name, value_text, _ in tdecl.enum_values:
                        parsed = parse_int_literal(value_text) if value_text else None
                        current = parsed if parsed is not None else current + 1
                        values[name.lower()] = current
                    ctx.enum_values[obj.name.lower()] = values
                elif tdecl.kind == "struct":
                    tokens = L.tokenize(obj.decl)
                    members = [_decl_source(obj.decl, tokens, m) for m in tdecl.members]
                    ctx.struct_members[obj.name.lower()] = (members, tdecl.header.extends)
        # Константы GVL: литералы и выражения из других констант (A := B * 2), до неподвижной точки
        changed = True
        while changed and pending:
            changed = False
            rest: list[tuple[str, list[str], str]] = []
            for gvl, names, init in pending:
                value = eval_int_text(init, ctx, ctx.gvl_int_constants[gvl])
                if value is None:
                    rest.append((gvl, names, init))
                    continue
                for name in names:
                    ctx.gvl_int_constants[gvl][name.lower()] = value
                changed = True
            pending = rest
        return ctx

    def int_constant(self, parts: Sequence[str], local: Mapping[str, int] | None = None) -> int | None:
        """Значение целой константы по имени: GVL.ИМЯ, Перечисление.Значение или ИМЯ (локальная,
        затем единственная с таким именем во всех GVL); None — неизвестно."""
        names = [p.lower() for p in parts]
        if len(names) >= 2:
            owner, member = names[-2], names[-1]
            table = self.gvl_int_constants.get(owner)
            if table is None:
                table = self.enum_values.get(owner)
            return None if table is None else table.get(member)
        if len(names) != 1:
            return None
        name = names[0]
        for scope in (local or {}, self.local_int_constants):
            if name in scope:
                return scope[name]
        found = {table[name] for table in self.gvl_int_constants.values() if name in table}
        return found.pop() if len(found) == 1 else None


def parse_int_literal(text: str) -> int | None:
    """Целое из литерала ST: 10, -3, 16#FF, 2#1010, INT#5; иначе None."""
    value = text.strip().replace("_", "")
    sign = 1
    if value.startswith(("-", "+")):
        sign = -1 if value[0] == "-" else 1
        value = value[1:].strip()
    match = re.fullmatch(r"(?:[A-Za-z]+#)?(?:(2|8|16)#([0-9A-Fa-f]+)|([0-9]+))", value)
    if not match:
        return None
    if match.group(3) is not None:
        return sign * int(match.group(3))
    return sign * int(match.group(2), int(match.group(1)))


Lookup = Callable[[Sequence[str]], int | None]


class _IntExpr:
    """Разбор и вычисление целого константного выражения ST: + - * / MOD, скобки, литералы, имена."""

    def __init__(self, tokens: Sequence[Token], sig: Sequence[int], a: int, b: int, lookup: Lookup) -> None:
        self.tokens = tokens
        self.sig = sig
        self.pos = a
        self.end = b
        self.lookup = lookup

    def peek(self) -> Token | None:
        return self.tokens[self.sig[self.pos]] if self.pos <= self.end else None

    def take(self) -> Token:
        tok = self.tokens[self.sig[self.pos]]
        self.pos += 1
        return tok

    def run(self) -> int | None:
        value = self.expr()
        return value if value is not None and self.pos == self.end + 1 else None

    def expr(self) -> int | None:
        value = self.term()
        while value is not None and (tok := self.peek()) is not None and tok.is_op("+", "-"):
            self.take()
            right = self.term()
            if right is None:
                return None
            value = value + right if tok.text == "+" else value - right
        return value

    def term(self) -> int | None:
        value = self.factor()
        while value is not None and (tok := self.peek()) is not None and (tok.is_op("*", "/") or tok.is_ident("MOD")):
            self.take()
            right = self.factor()
            if right is None or (right == 0 and not tok.is_op("*")):
                return None
            if tok.is_op("*"):
                value *= right
            else:
                quotient = abs(value) // abs(right) * (1 if (value >= 0) == (right >= 0) else -1)
                value = quotient if tok.is_op("/") else value - quotient * right
        return value

    def factor(self) -> int | None:
        tok = self.peek()
        if tok is None:
            return None
        if tok.is_op("-", "+"):
            self.take()
            value = self.factor()
            return None if value is None else (-value if tok.text == "-" else value)
        if tok.is_op("("):
            self.take()
            value = self.expr()
            closing = self.peek()
            if value is None or closing is None or not closing.is_op(")"):
                return None
            self.take()
            return value
        if tok.kind in (L.TK_NUMBER, L.TK_TYPED):
            self.take()
            if tok.kind == L.TK_TYPED and tok.text.split("#", 1)[0].upper() not in _INT_TYPES:
                return None
            return parse_int_literal(tok.text)
        if tok.kind == L.TK_IDENT:
            parts = [self.take().text]
            while (dot := self.peek()) is not None and dot.is_op(".") and self.pos + 1 <= self.end:
                name = self.tokens[self.sig[self.pos + 1]]
                if name.kind != L.TK_IDENT:
                    return None
                self.pos += 2
                parts.append(name.text)
            return self.lookup(parts)
        return None


def eval_int_tokens(tokens: Sequence[Token], sig: Sequence[int], a: int, b: int, lookup: Lookup) -> int | None:
    """Значение целого константного выражения из значимых токенов sig[a..b]; None — не вычисляется."""
    if a > b:
        return None
    return _IntExpr(tokens, sig, a, b, lookup).run()


def eval_int_text(text: str, ctx: Context, local: Mapping[str, int] | None = None) -> int | None:
    """Значение целого константного выражения из текста ('GVL_Const.N - 1', '16#FF')."""
    tokens = L.tokenize(text)
    sig = L.significant_indices(tokens)
    return eval_int_tokens(tokens, sig, 0, len(sig) - 1, lambda parts: ctx.int_constant(parts, local))


def fragment_int_constants(text: str, tokens: list[Token], ctx: Context) -> dict[str, int]:
    """Целые константы секций CONSTANT фрагмента (по порядку: следующие могут ссылаться на предыдущие)."""
    result: dict[str, int] = {}
    for block in L.parse_var_blocks(text, tokens):
        if "CONSTANT" not in block.modifiers or block.keyword not in ("VAR", "VAR_GLOBAL"):
            continue
        for decl in block.decls:
            value = eval_int_text(decl.init_text, ctx, result) if decl.init_text else None
            if value is not None:
                for name in decl.name_list:
                    result[name.lower()] = value
    return result


def _decl_source(text: str, tokens: Sequence[Token], decl: L.VarDecl) -> str:
    """Текст объявления одной строкой без комментариев: 'a, b : INT := 5;'."""
    end = decl.semi_index if decl.semi_index is not None else decl.last_index
    piece = L.strip_comments(text[tokens[decl.first_index].pos : tokens[end].end])
    piece = L.squash_ws(piece)
    return piece if piece.endswith(";") else piece + ";"


# ---------------------------------------------------------------------------
# Механика правок
# ---------------------------------------------------------------------------


class Edits:
    """Набор неперекрывающихся замен диапазонов текста с сохранением числа строк."""

    def __init__(self, text: str, tokens: list[Token]) -> None:
        self.text = text
        self.tokens = tokens
        self._edits: list[tuple[int, int, str]] = []

    def replace(self, first: int, last: int, replacement: str) -> None:
        """Заменяет токены first..last (индексы в полном списке, включительно)."""
        self._edits.append((self.tokens[first].pos, self.tokens[last].end, replacement))

    def insert_after(self, index: int, text: str) -> None:
        pos = self.tokens[index].end
        self._edits.append((pos, pos, text))

    def insert_before(self, index: int, text: str) -> None:
        pos = self.tokens[index].pos
        self._edits.append((pos, pos, text))

    def source(self, first: int, last: int) -> str:
        return self.text[self.tokens[first].pos : self.tokens[last].end]

    def apply(self) -> str:
        if not self._edits:
            return self.text
        out: list[str] = []
        cursor = 0
        for start, end, replacement in sorted(self._edits, key=lambda e: (e[0], e[1])):
            if start < cursor:
                continue  # перекрытие: оставляем первую правку
            removed = self.text[start:end]
            missing = removed.count("\n") - replacement.count("\n")
            out.append(self.text[cursor:start])
            out.append(replacement + "\n" * max(0, missing))
            cursor = end
        out.append(self.text[cursor:])
        return "".join(out)


Pass = Callable[[str, list[Token], list[int], Edits, Context], None]


def run_pass(text: str, func: Pass, ctx: Context) -> str:
    tokens = L.tokenize(text)
    sig = L.significant_indices(tokens)
    edits = Edits(text, tokens)
    func(text, tokens, sig, edits, ctx)
    return edits.apply()


def run_passes(text: str, passes: Sequence[Pass], ctx: Context) -> str:
    for func in passes:
        text = run_pass(text, func, ctx)
    return text


def _matching(tokens: list[Token], sig: list[int], k: int) -> int:
    """Позиция (в sig) парной скобки для открывающей скобки в позиции k; -1 — нет пары."""
    opening = tokens[sig[k]].text
    closing = {"(": ")", "[": "]"}[opening]
    depth = 0
    for j in range(k, len(sig)):
        tok = tokens[sig[j]]
        if tok.is_op(opening):
            depth += 1
        elif tok.is_op(closing):
            depth -= 1
            if depth == 0:
                return j
    return -1


def _designator_start(tokens: list[Token], sig: list[int], k: int) -> int:
    """Начало (в sig) обозначения a.b[i]^.c, заканчивающегося в позиции k; -1 — не обозначение."""
    j = k
    while j >= 0:
        tok = tokens[sig[j]]
        if tok.kind == L.TK_IDENT:
            if j > 0 and tokens[sig[j - 1]].is_op("."):
                j -= 2
                continue
            return j
        if tok.is_op("^"):
            j -= 1
            continue
        if tok.is_op("]"):
            depth = 0
            while j >= 0:
                if tokens[sig[j]].is_op("]"):
                    depth += 1
                elif tokens[sig[j]].is_op("["):
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            j -= 1
            continue
        return -1
    return -1


def _designator_end(tokens: list[Token], sig: list[int], k: int) -> int:
    """Конец (в sig) обозначения, начинающегося в позиции k."""
    j = k
    n = len(sig)
    if j >= n or tokens[sig[j]].kind != L.TK_IDENT:
        return -1
    while j + 1 < n:
        nxt = tokens[sig[j + 1]]
        if nxt.is_op(".") and j + 2 < n and tokens[sig[j + 2]].kind == L.TK_IDENT:
            j += 2
        elif nxt.is_op("^"):
            j += 1
        elif nxt.is_op("["):
            close = _matching(tokens, sig, j + 1)
            if close < 0:
                return j
            j = close
        else:
            break
    return j


def _statement_end(tokens: list[Token], sig: list[int], k: int) -> int:
    """Позиция (в sig) ';', завершающей оператор, начиная с k; -1 — не найдено."""
    depth = 0
    for j in range(k, len(sig)):
        tok = tokens[sig[j]]
        if tok.is_op("(", "["):
            depth += 1
        elif tok.is_op(")", "]"):
            depth -= 1
        elif tok.is_op(";") and depth <= 0:
            return j
    return -1


def _adjacent(tokens: list[Token], a: int, b: int) -> bool:
    return tokens[a].end == tokens[b].pos


def _at_statement_start(tokens: list[Token], sig: list[int], k: int) -> bool:
    if k == 0:
        return True
    prev = tokens[sig[k - 1]]
    return prev.is_op(";", ":") or prev.is_ident(*_STATEMENT_PRECEDERS)


# ---------------------------------------------------------------------------
# Общие проходы
# ---------------------------------------------------------------------------


def pass_strip_namespaces(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """NS.Name -> Name для пространств имён библиотек из --strip-namespace."""
    _strip_qualifiers(tokens, sig, ed, {ns.lower() for ns in ctx.strip_namespaces})


def pass_strip_gvl_qualifiers(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """GVL_Name.var -> var: в RuSTy у глобальных списков нет имён."""
    _strip_qualifiers(tokens, sig, ed, ctx.gvl_names)


def _strip_qualifiers(tokens: list[Token], sig: list[int], ed: Edits, names: set[str]) -> None:
    if not names:
        return
    for k in range(len(sig) - 2):
        tok = tokens[sig[k]]
        if tok.kind != L.TK_IDENT or tok.text.lower() not in names:
            continue
        if not tokens[sig[k + 1]].is_op(".") or tokens[sig[k + 2]].kind != L.TK_IDENT:
            continue
        if k > 0 and tokens[sig[k - 1]].is_op("."):
            continue
        ed.replace(sig[k], sig[k + 1], "")


def pass_set_reset(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """x S= e; -> IF e THEN x := TRUE; END_IF;  x R= e; -> IF e THEN x := FALSE; END_IF;"""
    for k in range(1, len(sig) - 1):
        tok = tokens[sig[k]]
        if not tok.is_ident("S", "R"):
            continue
        eq = tokens[sig[k + 1]]
        if not eq.is_op("=") or not _adjacent(tokens, sig[k], sig[k + 1]):
            continue
        start = _designator_start(tokens, sig, k - 1)
        end = _statement_end(tokens, sig, k + 2)
        if start < 0 or end < 0 or end == k + 2 or not _at_statement_start(tokens, sig, start):
            continue
        lhs = ed.source(sig[start], sig[k - 1])
        rhs = ed.source(sig[k + 2], sig[end - 1])
        value = "TRUE" if tok.upper == "S" else "FALSE"
        ed.replace(sig[start], sig[end], f"IF {rhs} THEN {lhs} := {value}; END_IF;")


def pass_string_size(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """STRING(80) -> STRING[80], WSTRING(80) -> WSTRING[80]."""
    for k in range(len(sig) - 1):
        if not tokens[sig[k]].is_ident("STRING", "WSTRING") or not tokens[sig[k + 1]].is_op("("):
            continue
        close = _matching(tokens, sig, k + 1)
        if close < 0:
            continue
        ed.replace(sig[k + 1], sig[k + 1], "[")
        ed.replace(sig[close], sig[close], "]")


def pass_var_sections(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """VAR_INST и VAR_STAT -> VAR (тип переменных тот же, время жизни — приближение)."""
    for k in sig:
        if tokens[k].is_ident("VAR_INST", "VAR_STAT"):
            ed.replace(k, k, "VAR")


def pass_drop_persistent(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """VAR_GLOBAL PERSISTENT RETAIN -> VAR_GLOBAL RETAIN."""
    for k in range(1, len(sig)):
        tok = tokens[sig[k]]
        prev = tokens[sig[k - 1]]
        if tok.is_ident("PERSISTENT") and prev.is_ident(*L.VAR_SECTION_KEYWORDS, *L.VAR_MODIFIERS):
            ed.replace(sig[k - 1] + 1, sig[k], "")


def pass_union_to_struct(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """UNION -> STRUCT (для проверки типов; раскладка памяти другая)."""
    for k in sig:
        if tokens[k].is_ident("UNION"):
            ed.replace(k, k, "STRUCT")
        elif tokens[k].is_ident("END_UNION"):
            ed.replace(k, k, "END_STRUCT")


# ---------------------------------------------------------------------------
# Проходы RuSTy
# ---------------------------------------------------------------------------


def pass_itf_null_checks(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """itfX <> 0 -> __ItfIsSet(ADR(itfX)); itfX = 0 -> (NOT __ItfIsSet(ADR(itfX)))."""
    n = len(sig)
    for k in range(n):
        op = tokens[sig[k]]
        if not op.is_op("<>", "="):
            continue
        # itfX <> 0
        if k + 1 < n and k > 0 and _is_zero(tokens, sig, k + 1):
            start = _designator_start(tokens, sig, k - 1)
            if start >= 0 and _is_itf_designator(tokens, sig, start, k - 1):
                ed.replace(sig[start], sig[k + 1], _itf_check(ed.source(sig[start], sig[k - 1]), op.text))
                ctx.used_itf_helper = True
                continue
        # 0 <> itfX
        if k > 0 and k + 1 < n and _is_zero(tokens, sig, k - 1):
            if k - 2 >= 0 and tokens[sig[k - 2]].is_op("."):
                continue
            end = _designator_end(tokens, sig, k + 1)
            if end >= 0 and _is_itf_designator(tokens, sig, k + 1, end):
                ed.replace(sig[k - 1], sig[end], _itf_check(ed.source(sig[k + 1], sig[end]), op.text))
                ctx.used_itf_helper = True


def _is_zero(tokens: list[Token], sig: list[int], k: int) -> bool:
    tok = tokens[sig[k]]
    if tok.kind != L.TK_NUMBER or tok.text != "0":
        return False
    nxt = tokens[sig[k + 1]] if k + 1 < len(sig) else None
    return nxt is None or not nxt.is_op(".", "[", "^")


def _is_itf_designator(tokens: list[Token], sig: list[int], start: int, end: int) -> bool:
    last = tokens[sig[end]]
    return last.kind == L.TK_IDENT and bool(_ITF_NAME_RE.match(last.text)) and start <= end


def _itf_check(designator: str, op: str) -> str:
    call = f"{ITF_HELPER_NAME}(ADR({designator}))"
    return call if op == "<>" else f"(NOT {call})"


def pass_isvalidref(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """__ISVALIDREF(x) -> (ADR(x) <> 0)."""
    for k in range(len(sig) - 1):
        if tokens[sig[k]].is_ident("__ISVALIDREF") and tokens[sig[k + 1]].is_op("("):
            close = _matching(tokens, sig, k + 1)
            if close > k + 2:
                inner = ed.source(sig[k + 2], sig[close - 1])
                ed.replace(sig[k], sig[close], f"(ADR({inner}) <> 0)")


def pass_flatten_struct_extends(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """TYPE ST_B EXTENDS ST_A : STRUCT ... -> поля ST_A вставляются в начало ST_B."""
    tdecl = L.parse_type_decl(text, tokens)
    if tdecl is None or tdecl.kind != "struct" or not tdecl.header.extends:
        return
    if tdecl.header.extends_range is None or tdecl.body_start_index is None:
        return
    members = _inherited_members(ctx, tdecl.header.extends[0], set())
    if members is None:
        return
    first, last = tdecl.header.extends_range
    ed.replace(first - 1 if tokens[first - 1].kind == L.TK_WS else first, last, "")
    if members:
        ed.insert_after(tdecl.body_start_index, " " + " ".join(members))


def _inherited_members(ctx: Context, base: str, seen: set[str]) -> list[str] | None:
    key = base.lower()
    if key in seen or key not in ctx.struct_members:
        return None
    seen.add(key)
    members, extends = ctx.struct_members[key]
    if extends:
        parent = _inherited_members(ctx, extends[0], seen)
        if parent is None:
            return None
        return parent + members
    return list(members)


def pass_rename_types(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """CTU/CTD/CTUD в объявлениях -> CDS_* (прокладки с сигнатурой CODESYS Standard)."""
    for k in range(1, len(sig)):
        tok = tokens[sig[k]]
        if tok.kind != L.TK_IDENT or tok.upper not in RUSTY_TYPE_RENAMES:
            continue
        prev = tokens[sig[k - 1]]
        if prev.is_op(":") or prev.is_ident("OF", "EXTENDS"):
            ed.replace(sig[k], sig[k], RUSTY_TYPE_RENAMES[tok.upper])


def pass_inout_constant(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """VAR_IN_OUT CONSTANT -> VAR_IN_OUT: RuSTy не знает этот модификатор (E034, E036 в вызовах).
    Запрет записи в параметр при этом не проверяется — его проверяет компилятор CODESYS."""
    for k in range(1, len(sig)):
        if tokens[sig[k]].is_ident("CONSTANT") and tokens[sig[k - 1]].is_ident("VAR_IN_OUT"):
            ed.replace(sig[k - 1] + 1, sig[k], "")


RUSTY_PASSES: list[Pass] = [
    pass_flatten_struct_extends,
    pass_strip_namespaces,
    pass_strip_gvl_qualifiers,
    pass_set_reset,
    pass_itf_null_checks,
    pass_isvalidref,
    pass_string_size,
    pass_var_sections,
    pass_drop_persistent,
    pass_inout_constant,
    pass_union_to_struct,
    pass_rename_types,
]


def rusty_text(text: str, ctx: Context) -> str:
    """Применяет все замены RuSTy к фрагменту текста."""
    return run_passes(text, RUSTY_PASSES, ctx)


# ---------------------------------------------------------------------------
# Проходы iec-checker (понижение для разборщика iec_checker v0.4)
# ---------------------------------------------------------------------------


def pass_remove_pragmas(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """{attribute ...} и другие прагмы удаляются."""
    for i, tok in enumerate(tokens):
        if tok.kind == L.TK_PRAGMA:
            ed.replace(i, i, "")


def pass_c_comments(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """/* ... */ -> (* ... *)."""
    for i, tok in enumerate(tokens):
        if tok.kind == L.TK_COMMENT and tok.text.startswith("/*"):
            body = tok.text[2:-2] if tok.text.endswith("*/") else tok.text[2:]
            body = body.replace("(*", "( *").replace("*)", "* )")
            ed.replace(i, i, f"(*{body}*)")


def pass_ref_assign(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """r REF= x; -> r := ADR(x);"""
    for k in range(len(sig) - 1):
        if not tokens[sig[k]].is_ident("REF") or not tokens[sig[k + 1]].is_op("="):
            continue
        if not _adjacent(tokens, sig[k], sig[k + 1]):
            continue
        end = _statement_end(tokens, sig, k + 2)
        if end < 0 or end == k + 2:
            continue
        ed.replace(sig[k], sig[k + 2] - 1, ":= ADR(")
        ed.replace(sig[end], sig[end], ");")


def pass_remove_deref(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """THIS^. и SUPER^. убираются, p^ -> p (разборщик не знает разыменования)."""
    n = len(sig)
    skip: set[int] = set()
    for k in range(n):
        if k in skip:
            continue
        tok = tokens[sig[k]]
        if (
            tok.is_ident("THIS", "SUPER")
            and k + 2 < n
            and tokens[sig[k + 1]].is_op("^")
            and tokens[sig[k + 2]].is_op(".")
        ):
            ed.replace(sig[k], sig[k + 2], "")
            skip.update((k + 1, k + 2))
        elif tok.is_op("^"):
            ed.replace(sig[k], sig[k], "")


def super_calls_pass(base: str | None) -> Pass:
    """SUPER^.M( -> <Base>__M( (метод базового FB после понижения стал функцией)."""

    def run(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
        if not base:
            return
        for k in range(len(sig) - 3):
            if (
                tokens[sig[k]].is_ident("SUPER")
                and tokens[sig[k + 1]].is_op("^")
                and tokens[sig[k + 2]].is_op(".")
                and tokens[sig[k + 3]].kind == L.TK_IDENT
            ):
                ed.replace(sig[k], sig[k + 3], f"{base}__{tokens[sig[k + 3]].text}")

    return run


def pass_pointer_to_ref(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """POINTER TO / REFERENCE TO -> REF_TO."""
    for k in range(len(sig) - 1):
        if tokens[sig[k]].is_ident("POINTER", "REFERENCE") and tokens[sig[k + 1]].is_ident("TO"):
            ed.replace(sig[k], sig[k + 1], "REF_TO")


def pass_subrange(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """INT(0..100) -> INT.

    Исключение — псевдоним типа с десятичными границами (TYPE T_Pct : INT(0..100) := 50;): там
    iec_checker v0.4 поддиапазон разбирает и проверяет начальное значение (OutOfBounds), поэтому он
    остаётся. В секциях VAR и полях структур поддиапазон — ParserError, границы 16#.. — тоже.
    """
    tdecl = L.parse_type_decl(text, tokens)
    alias = tdecl is not None and tdecl.kind == "alias"
    for k in range(len(sig) - 1):
        if not tokens[sig[k]].is_ident(*_INT_TYPES) or not tokens[sig[k + 1]].is_op("("):
            continue
        close = _matching(tokens, sig, k + 1)
        if close < 0 or not any(tokens[sig[j]].is_op("..") for j in range(k + 2, close)):
            continue
        if alias and k > 0 and tokens[sig[k - 1]].is_op(":"):
            bounds = _split_top(tokens, sig, k + 2, close - 1, "..")
            if len(bounds) == 2 and all(_plain_int(tokens, sig, a, b) for a, b in bounds):
                continue
        ed.replace(sig[k + 1], sig[close], "")


def pass_array_star(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """ARRAY[*] -> ARRAY[0..0] (массив переменной длины)."""
    for k in range(len(sig) - 1):
        if not tokens[sig[k]].is_ident("ARRAY") or not tokens[sig[k + 1]].is_op("["):
            continue
        close = _matching(tokens, sig, k + 1)
        if close < 0:
            continue
        # только измерение из одной '*' (ARRAY[*], ARRAY[*, *]), а не умножение в границе
        for a, b in _split_top(tokens, sig, k + 2, close - 1, ","):
            if a == b and tokens[sig[a]].is_op("*"):
                ed.replace(sig[a], sig[a], "0..0")


def pass_lower_types(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """DUT: EXTENDS у структур убирается, массивы в структурах -> тип элемента (без начального
    значения [...]), базовый тип перечисления убирается."""
    tdecl = L.parse_type_decl(text, tokens)
    if tdecl is None:
        return
    if tdecl.kind == "struct" and tdecl.header.extends_range is not None:
        first, last = tdecl.header.extends_range
        ed.replace(first - 1 if tokens[first - 1].kind == L.TK_WS else first, last, "")
    if tdecl.kind in ("struct", "union"):
        for member in tdecl.members:
            if member.type_range is None:
                continue
            first, last = member.type_range
            if not tokens[first].is_ident("ARRAY"):
                continue
            # тип элемента — после последнего OF (ARRAY[..] OF ARRAY[..] OF INT -> INT)
            of_index = max((i for i in range(first, last + 1) if tokens[i].is_ident("OF")), default=None)
            if of_index is None or of_index >= last:
                continue
            element = L.squash_ws(L.strip_comments(ed.source(of_index + 1, last)))
            ed.replace(first, last, element)
            if member.assign_index is not None and member.init_range is not None:
                start = member.assign_index
                if start > 0 and tokens[start - 1].kind == L.TK_WS:
                    start -= 1
                ed.replace(start, member.init_range[1], "")
    if tdecl.kind == "enum" and tdecl.enum_base_range is not None:
        first, last = tdecl.enum_base_range
        ed.replace(first, last, "")


def _is_literal(tokens: list[Token], sig: list[int], a: int, b: int) -> bool:
    """Литерал (с необязательным знаком) или массив литералов [l, l] без повторителей."""

    def single(j: int, end: int) -> int:
        if j <= end and tokens[sig[j]].is_op("-", "+"):
            j += 1
        if j > end:
            return -1
        tok = tokens[sig[j]]
        if tok.kind in (L.TK_NUMBER, L.TK_STRING, L.TK_WSTRING):
            return j + 1
        if tok.kind == L.TK_TYPED and tok.text.split("#", 1)[0].upper() in _ELEMENTARY_TYPES:
            return j + 1
        if tok.is_ident("TRUE", "FALSE"):
            return j + 1
        return -1

    if a > b:
        return False
    if tokens[sig[a]].is_op("["):
        if not tokens[sig[b]].is_op("]"):
            return False
        j = a + 1
        while j < b:
            j = single(j, b - 1)
            if j < 0:
                return False
            if j < b and tokens[sig[j]].is_op(","):
                j += 1
            elif j != b:
                return False
        return True
    return single(a, b) == b + 1


def pass_drop_nonliteral_inits(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Начальные значения, не являющиеся литералами, удаляются (разборщик их не понимает)."""
    decls: list[L.VarDecl] = []
    for block in L.parse_var_blocks(text, tokens):
        decls.extend(block.decls)
    tdecl = L.parse_type_decl(text, tokens)
    if tdecl is not None:
        decls.extend(tdecl.members)
    pos_of = {index: k for k, index in enumerate(sig)}
    local = fragment_int_constants(text, tokens, ctx)

    def constant(parts: Sequence[str]) -> int | None:
        # только константы GVL и VAR CONSTANT: значение перечисления целым не подставляется
        if len(parts) >= 2 and parts[-2].lower() not in ctx.gvl_int_constants:
            return None
        return ctx.int_constant(parts, local)

    for decl in decls:
        if decl.assign_index is None or decl.init_range is None:
            continue
        a = pos_of[decl.init_range[0]]
        b = pos_of[decl.init_range[1]]
        if _is_literal(tokens, sig, a, b):
            continue
        value = eval_int_tokens(tokens, sig, a, b, constant)
        if value is not None:
            # целое константное выражение (:= GVL_Const.N - 1) -> его значение
            ed.replace(decl.init_range[0], decl.init_range[1], str(value))
            continue
        start = decl.assign_index
        if start > 0 and tokens[start - 1].kind == L.TK_WS:
            start -= 1
        ed.replace(start, decl.init_range[1], "")


def pass_case_labels(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Метки CASE вида E_Enum.Value и GVL_Const.NAME -> их целые значения."""
    labels = set(L.case_label_indices(tokens, sig))
    pos_of = {index: k for k, index in enumerate(sig)}
    for index in sorted(labels):
        k = pos_of[index]
        if k + 2 >= len(sig) or sig[k + 2] not in labels:
            continue
        owner = tokens[sig[k]]
        if owner.kind != L.TK_IDENT or not tokens[sig[k + 1]].is_op("."):
            continue
        if k > 0 and tokens[sig[k - 1]].is_op("."):
            continue
        member = tokens[sig[k + 2]].text.lower()
        table = ctx.enum_values.get(owner.text.lower()) or ctx.gvl_int_constants.get(owner.text.lower())
        if table and member in table:
            ed.replace(sig[k], sig[k + 2], str(table[member]))


_ST_ESCAPES = {"$": "$", "'": "'", '"': '"', "L": "\n", "N": "\n", "P": "\f", "R": "\r", "T": "\t"}


def decode_st_string(body: str, wide: bool) -> str:
    """Раскрывает экранирование $ в теле строкового литерала ST."""
    out: list[str] = []
    i = 0
    width = 4 if wide else 2
    while i < len(body):
        char = body[i]
        if char == "$" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt.upper() in _ST_ESCAPES:
                out.append(_ST_ESCAPES[nxt.upper()] if nxt not in "$'\"" else nxt)
                i += 2
                continue
            hexpart = body[i + 1 : i + 1 + width]
            if len(hexpart) == width and all(c in "0123456789abcdefABCDEF" for c in hexpart):
                out.append(chr(int(hexpart, 16)))
                i += 1 + width
                continue
        out.append(char)
        i += 1
    return "".join(out)


_SAFE_STRING_CHARS = set("".join(chr(c) for c in range(0x21, 0x7F))) - {"$", "'", '"'}


def encode_iec_checker_string(value: str, wide: bool) -> str:
    """Тело литерала только из символов, которые принимает лексер iec_checker v0.4."""
    out: list[str] = []
    for char in value:
        if char in _SAFE_STRING_CHARS:
            out.append(char)
        elif wide:
            code = ord(char)
            out.append("$%04X" % (code if code <= 0xFFFF else 0x3F))
        else:
            code = ord(char)
            out.append("$%02X" % (code if code < 0x80 else 0x3F))
    return "".join(out)


def pass_string_literals(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Пробелы, $ и не-ASCII в строковых литералах -> шестнадцатеричные $-коды."""
    for k in sig:
        tok = tokens[k]
        if tok.kind not in (L.TK_STRING, L.TK_WSTRING) or len(tok.text) < 2:
            continue
        quote = tok.text[0]
        if not tok.text.endswith(quote):
            continue
        wide = tok.kind == L.TK_WSTRING
        value = decode_st_string(tok.text[1:-1], wide)
        encoded = quote + encode_iec_checker_string(value, wide) + quote
        if encoded != tok.text:
            ed.replace(k, k, encoded)


def pass_underscore_idents(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Идентификаторы с ведущим '_' (__NEW, __QUERYINTERFACE) -> CDS__NEW (лексер iec_checker)."""
    for k in sig:
        tok = tokens[k]
        if tok.kind == L.TK_IDENT and tok.text.startswith("_"):
            ed.replace(k, k, "CDS" + tok.text)


def _plain_int(tokens: list[Token], sig: list[int], a: int, b: int, signed: bool = True) -> bool:
    """Токены sig[a..b] — десятичное целое (со знаком, если signed): так iec_checker пишет границы."""
    if signed and a < b and tokens[sig[a]].is_op("-", "+"):
        a += 1
    return a == b and tokens[sig[a]].kind == L.TK_NUMBER and tokens[sig[a]].text.replace("_", "").isdigit()


def _split_top(tokens: list[Token], sig: list[int], a: int, b: int, sep: str) -> list[tuple[int, int]]:
    """Диапазоны (в sig) между разделителями sep верхнего уровня скобок в sig[a..b]."""
    parts: list[tuple[int, int]] = []
    depth = 0
    start = a
    for j in range(a, b + 1):
        tok = tokens[sig[j]]
        if tok.is_op("(", "["):
            depth += 1
        elif tok.is_op(")", "]"):
            depth -= 1
        elif tok.is_op(sep) and depth == 0:
            parts.append((start, j - 1))
            start = j + 1
    parts.append((start, b))
    return parts


def pass_constant_sizes(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Границы массивов и длины строк — константные выражения -> целые литералы.

    ARRAY[0..GVL_Const.N - 1] -> ARRAY[0..7] по значениям констант GVL, перечислений и VAR CONSTANT
    объекта; не вычисляется — ARRAY[0..32767] (широкий диапазон). STRING[GVL_Const.LEN] -> STRING[80];
    не вычисляется — STRING без длины. Разборщик iec_checker v0.4 принимает здесь только числа.
    """
    local = fragment_int_constants(text, tokens, ctx)

    def value(a: int, b: int) -> int | None:
        return eval_int_tokens(tokens, sig, a, b, lambda parts: ctx.int_constant(parts, local))

    for k in range(len(sig) - 1):
        tok = tokens[sig[k]]
        if not tokens[sig[k + 1]].is_op("["):
            continue
        if k > 0 and tokens[sig[k - 1]].is_op("."):
            continue
        close = _matching(tokens, sig, k + 1)
        if close < 0:
            continue
        if tok.is_ident("ARRAY"):
            for a, b in _split_top(tokens, sig, k + 2, close - 1, ","):
                bounds = _split_top(tokens, sig, a, b, "..")
                if len(bounds) != 2 or a > b:
                    continue
                (la, lb), (ha, hb) = bounds
                if _plain_int(tokens, sig, la, lb) and _plain_int(tokens, sig, ha, hb):
                    continue
                low = value(la, lb)
                high = value(ha, hb)
                if low is None:
                    low = min(0, high) if high is not None else 0
                if high is None:
                    high = low + DUMMY_ARRAY_SPAN
                ed.replace(sig[a], sig[b], f"{low}..{high}")
        elif tok.is_ident("STRING", "WSTRING"):
            if _plain_int(tokens, sig, k + 2, close - 1, signed=False):
                continue
            length = value(k + 2, close - 1)
            if length is None or length < 1:
                ed.replace(sig[k + 1], sig[close], "")
            else:
                ed.replace(sig[k + 2], sig[close - 1], str(length))


def pass_nested_arrays(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """ARRAY[a] OF ARRAY[b] OF T -> ARRAY[a, b] OF T (вложенных массивов в грамматике нет)."""
    for k in range(len(sig) - 3):
        if (
            tokens[sig[k]].is_op("]")
            and tokens[sig[k + 1]].is_ident("OF")
            and tokens[sig[k + 2]].is_ident("ARRAY")
            and tokens[sig[k + 3]].is_op("[")
        ):
            ed.replace(sig[k], sig[k + 3], ", ")


def pass_time_calls(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """TIME() -> CDS__TIME(), LTIME() -> CDS__LTIME(): в грамматике iec_checker нет этих операторов
    (TIME и LTIME — ключевые слова типов).

    Замена — вызов несуществующей функции без аргументов, как и сам оператор: значение и тип для
    iec_checker неизвестны. Литерал длительности на этом месте давал бы ложные находки: iec_checker 0.4
    считает любой литерал длительности в делителе нулём (ZeroDivision), а сравнение с ним через = и
    <> в условии — PLCOPEN-CP28 (проверено бинарником v0.4).
    """
    for k in range(len(sig) - 2):
        tok = tokens[sig[k]]
        if not tok.is_ident("TIME", "LTIME") or (k > 0 and tokens[sig[k - 1]].is_op(".")):
            continue
        if tokens[sig[k + 1]].is_op("(") and tokens[sig[k + 2]].is_op(")"):
            ed.replace(sig[k], sig[k + 2], f"{TIME_FUNCTION_PREFIX}{tok.upper}()")


def normalize_duration(prefix: str, value: str) -> str | None:
    """T#1h500ms -> T#1H0M0S500MS: iec_checker v0.4 требует единицы подряд, от старшей к младшей,
    в верхнем регистре и без '_'; None — значение не разобрано."""
    body = value.replace("_", "")
    sign = ""
    if body[:1] in ("-", "+"):
        sign, body = body[0], body[1:]
    parts: list[tuple[str, str]] = []
    pos = 0
    while pos < len(body):
        match = _DURATION_PART_RE.match(body, pos)
        if match is None:
            return None
        parts.append((match.group(1), match.group(2).upper()))
        pos = match.end()
    if not parts:
        return None
    order = [_DURATION_UNITS.index(unit) for _, unit in parts]
    if any(b <= a for a, b in itertools.pairwise(order)):
        return None
    values = {unit: number for number, unit in parts}
    units = _DURATION_UNITS[order[0] : order[-1] + 1]
    return f"{prefix}#{sign}" + "".join(values.get(unit, "0") + unit for unit in units)


def _normalize_real(text: str) -> str:
    """1E3 -> 1.0E3, 1.5e3 -> 1.5E3: iec_checker v0.4 принимает экспоненту только с дробной частью."""
    if "#" in text:
        return text
    match = re.fullmatch(r"([0-9_]+)(\.[0-9_]+)?(?:[eE]([-+]?[0-9_]+))?", text)
    if match is None or match.group(3) is None:
        return text
    return f"{match.group(1)}{match.group(2) or '.0'}E{match.group(3)}"


def pass_literals(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Литералы в формы, которые принимает лексер iec_checker v0.4.

    Длительности: единицы подряд в верхнем регистре (T#1h500ms -> T#1H0M0S500MS, t#5s -> T#5S);
    префиксы дат и времени суток — в верхнем регистре; WORD#16#FF -> 16#FF (типизированных литералов
    битовых строк в грамматике нет); BOOL#1 -> TRUE; REAL#1 -> REAL#1.0; 1E3 -> 1.0E3.
    """
    for k in sig:
        tok = tokens[k]
        new = tok.text
        if tok.kind == L.TK_NUMBER:
            new = _normalize_real(tok.text)
        elif tok.kind == L.TK_TYPED:
            prefix, value = tok.text.split("#", 1)
            upper = prefix.upper()
            if upper in _DURATION_PREFIXES:
                new = normalize_duration(upper, value) or f"{upper}#{value}"
            elif upper in _DATE_PREFIXES:
                new = f"{upper}#{value}"
            elif upper in _BIT_STRING_TYPES:
                new = value
            elif upper == "BOOL":
                new = "TRUE" if value.upper() in ("TRUE", "1") else "FALSE"
            elif upper in _REAL_TYPES:
                number = value.lstrip("+-")
                sign = value[: len(value) - len(number)]
                number = _normalize_real(number)
                if number.replace("_", "").isdigit():
                    number += ".0"
                new = f"{upper}#{sign}{number}"
        if new != tok.text:
            ed.replace(k, k, new)


def pass_short_circuit(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """AND_THEN -> AND, OR_ELSE -> OR (расширения CODESYS; порядок вычисления не важен для анализа)."""
    for k in sig:
        if tokens[k].is_ident("AND_THEN"):
            ed.replace(k, k, "AND")
        elif tokens[k].is_ident("OR_ELSE"):
            ed.replace(k, k, "OR")


def _index_text(subscripts: list[str]) -> str:
    """Индексы a[i][j] / a[i, j] -> 'i' или 'CDS__IDX(i, j)' (в выражениях разборщик ждёт один индекс)."""
    joined = ", ".join(subscripts)
    return joined if len(subscripts) == 1 and "," not in joined else f"{INDEX_FUNCTION}({joined})"


def pass_element_access(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Обращения к элементам массивов, которых нет в грамматике iec_checker v0.4.

    a[i].x -> a.x[i]; a[i].b[j].c -> a.b.c[CDS__IDX(i, j)]; a[i, j] и a[i][j] -> a[CDS__IDX(i, j)];
    вызов a[i](...) и a[i].M(...) -> a(..., i) и a.M(..., i). Индексы остаются в тексте (у вызова —
    лишними аргументами), но обращение уже не к элементу: только для статанализа. Вложенные
    обращения (b[a[i].x].y) обрабатываются повторными проходами: правка внешнего обращения
    перекрывает правки вложенных, и они выполняются на следующем проходе.
    """
    n = len(sig)
    for k in range(n):
        tok = tokens[sig[k]]
        if tok.kind != L.TK_IDENT or tok.is_ident("ARRAY", "STRING", "WSTRING"):
            continue
        if k > 0 and tokens[sig[k - 1]].is_op("."):
            continue
        names = [tok.text]
        subscripts: list[str] = []
        multi = False  # индекс не в конце обозначения, несколько индексов или индекс из нескольких выражений
        j = k
        while j + 1 < n:
            nxt = tokens[sig[j + 1]]
            if nxt.is_op(".") and j + 2 < n and tokens[sig[j + 2]].kind in (L.TK_IDENT, L.TK_NUMBER):
                multi = multi or bool(subscripts)
                names.append(tokens[sig[j + 2]].text)
                j += 2
            elif nxt.is_op("["):
                close = _matching(tokens, sig, j + 1)
                if close < 0 or close == j + 2 or any(tokens[sig[i]].is_op("..") for i in range(j + 2, close)):
                    break
                inner = L.squash_ws(L.strip_comments(ed.source(sig[j + 2], sig[close - 1]))).strip()
                multi = multi or bool(subscripts) or len(_split_top(tokens, sig, j + 2, close - 1, ",")) > 1
                subscripts.append(inner)
                j = close
            else:
                break
        if not subscripts:
            continue
        designator = ".".join(names)
        call = j + 1 < n and tokens[sig[j + 1]].is_op("(")
        if call:
            # a[i](...) / a[i].M(...) -> a(..., i) / a.M(..., i): индексы — лишними аргументами
            paren = _matching(tokens, sig, j + 1)
            if paren < 0:
                continue
            ed.replace(sig[k], sig[j], designator)
            ed.insert_before(sig[paren], (", " if paren > j + 2 else "") + ", ".join(subscripts))
        elif multi:
            ed.replace(sig[k], sig[j], f"{designator}[{_index_text(subscripts)}]")


def pass_keyword_idents(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Имена — ключевые слова iec_checker (Priority, Interval, On, ...) -> Priority_, Interval_, On_."""
    for k in sig:
        tok = tokens[k]
        if tok.kind == L.TK_IDENT and tok.upper in IEC_CHECKER_RESERVED:
            ed.replace(k, k, tok.text + "_")


def pass_upper_keywords(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """if/then/end_if/... и true/false -> верхний регистр (лексер iec_checker различает регистр)."""
    for k in sig:
        tok = tokens[k]
        if tok.kind == L.TK_IDENT and tok.upper in _CASE_SENSITIVE_KEYWORDS and tok.text != tok.upper:
            ed.replace(k, k, tok.upper)


def _case_colons(tokens: list[Token], sig: list[int]) -> set[int]:
    """Позиции (в sig) двоеточий меток CASE: внутри CASE ... END_CASE других ':' в теле нет."""
    result: set[int] = set()
    depth = 0
    for k, index in enumerate(sig):
        tok = tokens[index]
        if tok.is_ident("CASE"):
            depth += 1
        elif tok.is_ident("END_CASE"):
            depth = max(0, depth - 1)
        elif depth and tok.is_op(":"):
            result.add(k)
    return result


def pass_empty_statements(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Пустой оператор ';' удаляется (в грамматике iec_checker v0.4 его нет); строки сохраняются."""
    colons = _case_colons(tokens, sig)
    for k, index in enumerate(sig):
        if not tokens[index].is_op(";"):
            continue
        prev = tokens[sig[k - 1]] if k > 0 else None
        if prev is None or prev.is_op(";") or prev.is_ident("THEN", "ELSE", "DO", "REPEAT") or (k - 1) in colons:
            ed.replace(index, index, "")


def pass_empty_branches(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """Пустые ветви IF/CASE и тела циклов (в том числе только с комментарием) -> CDS__NOP();

    iec_checker v0.4 требует в ветви хотя бы один оператор. CDS__NOP — вызов несуществующей
    функции без аргументов: разбирается и не даёт находок.
    """
    colons = _case_colons(tokens, sig)
    closers = {
        "THEN": ("ELSIF", "ELSE", "END_IF"),
        "ELSE": ("END_IF", "END_CASE"),
        "DO": ("END_FOR", "END_WHILE"),
        "REPEAT": ("UNTIL",),
    }
    for k in range(len(sig) - 1):
        tok = tokens[sig[k]]
        nxt = tokens[sig[k + 1]]
        if tok.kind == L.TK_IDENT and tok.upper in closers:
            empty = nxt.is_ident(*closers[tok.upper])
        elif k in colons:
            empty = nxt.is_ident("ELSE", "END_CASE") or L._match_label_list(tokens, sig, k + 1) > 0
        else:
            continue
        if empty:
            ed.insert_after(sig[k], " " + NOP_CALL)


IEC_CHECKER_PASSES: list[Pass] = [
    pass_flatten_struct_extends,
    pass_remove_pragmas,
    pass_c_comments,
    pass_strip_namespaces,
    pass_set_reset,
    pass_ref_assign,
    pass_isvalidref,
    pass_remove_deref,
    pass_pointer_to_ref,
    pass_var_sections,
    pass_drop_persistent,
    pass_string_size,
    pass_subrange,
    pass_array_star,
    pass_constant_sizes,
    pass_nested_arrays,
    pass_union_to_struct,
    pass_lower_types,
    pass_drop_nonliteral_inits,
    pass_case_labels,
    pass_time_calls,
    pass_literals,
    pass_short_circuit,
    *[pass_element_access] * ELEMENT_ACCESS_PASSES,
    pass_string_literals,
    pass_underscore_idents,
    pass_keyword_idents,
    pass_upper_keywords,
    pass_empty_statements,
    pass_empty_branches,
]


def iec_checker_text(text: str, ctx: Context, base: str | None = None) -> str:
    """Применяет все понижения iec-checker к фрагменту текста.

    base — базовый FB текущего POU (для SUPER^.M -> <base>__M).
    """
    return run_passes(text, [super_calls_pass(base), *IEC_CHECKER_PASSES], ctx)


# ---------------------------------------------------------------------------
# Правки заголовков (используются сборкой)
# ---------------------------------------------------------------------------


def edit_header(
    text: str,
    *,
    keyword: str | None = None,
    name: str | None = None,
    drop_modifiers: bool = False,
    drop_extends: bool = False,
    drop_implements: bool = False,
    return_type: str | None = None,
    default_return_type: str | None = None,
) -> str:
    """Меняет заголовок объявления: ключевое слово, имя, модификаторы, наследование, тип."""
    tokens = L.tokenize(text)
    hdr = L.parse_header(text, tokens)
    if hdr is None:
        return text
    ed = Edits(text, tokens)
    if keyword is not None:
        ed.replace(hdr.keyword_index, hdr.keyword_index, keyword)
    if drop_modifiers:
        for index in hdr.modifier_indices:
            last = index + 1 if index + 1 < len(tokens) and tokens[index + 1].kind == L.TK_WS else index
            ed.replace(index, last, "")
    if name is not None and hdr.name_index is not None:
        ed.replace(hdr.name_index, hdr.name_index, name)
    for flag, rng in ((drop_extends, hdr.extends_range), (drop_implements, hdr.implements_range)):
        if flag and rng is not None:
            first, last = rng
            if first > 0 and tokens[first - 1].kind == L.TK_WS and "\n" not in tokens[first - 1].text:
                first -= 1
            ed.replace(first, last, "")
    if return_type is not None and hdr.return_type_range is not None:
        ed.replace(hdr.return_type_range[0], hdr.return_type_range[1], return_type)
    elif default_return_type is not None and hdr.return_type_range is None and hdr.name_index is not None:
        ed.insert_after(hdr.name_index, " : " + default_return_type)
    return ed.apply()


def referenced_names(*texts: str) -> set[str]:
    """Имена (нижний регистр), на которые ссылаются тексты: идентификаторы не после '.'."""
    names: set[str] = set()
    for text in texts:
        tokens = L.tokenize(text)
        sig = L.significant_indices(tokens)
        for k, index in enumerate(sig):
            tok = tokens[index]
            if tok.kind != L.TK_IDENT:
                continue
            if k > 0 and tokens[sig[k - 1]].is_op("."):
                this_member = k >= 3 and tokens[sig[k - 2]].is_op("^") and tokens[sig[k - 3]].is_ident("THIS", "SUPER")
                if not this_member:
                    continue
            names.add(tok.text.lower())
    return names


def declared_names(text: str) -> set[str]:
    names: set[str] = set()
    for block in L.parse_var_blocks(text):
        for decl in block.decls:
            names.update(n.lower() for n in decl.name_list)
    return names


def var_decls_source(text: str) -> list[tuple[list[str], str]]:
    """Объявления переменных: [(имена, 'T := init;')] — часть после ':' без комментариев."""
    tokens = L.tokenize(text)
    result: list[tuple[list[str], str]] = []
    for block in L.parse_var_blocks(text, tokens):
        for decl in block.decls:
            if decl.colon_index is None:
                continue
            end = decl.semi_index if decl.semi_index is not None else decl.last_index
            if end <= decl.colon_index:
                continue
            rest = text[tokens[decl.colon_index].end : tokens[end].end]
            rest = L.squash_ws(L.strip_comments(rest))
            result.append((decl.name_list, rest if rest.endswith(";") else rest + ";"))
    return result
