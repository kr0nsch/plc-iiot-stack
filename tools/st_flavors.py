"""Совместимые замены текста ST для вариантов сборки rusty и iec-checker.

Каждый проход — функция «текст -> текст» на токенах stlayout. Проходы сохраняют
число строк фрагмента (удалённые переводы строк возвращаются в конец замены), поэтому
карта строк build/assembled/sourcemap.json остаётся точной. Таблицы правил — в
tools/README.md («Варианты сборки»).
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Iterable, Sequence
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
    struct_members: dict[str, tuple[list[str], list[str]]] = field(default_factory=dict)
    strip_namespaces: list[str] = field(default_factory=list)
    used_itf_helper: bool = False

    @classmethod
    def from_objects(cls, objects: Iterable[L.StObject], strip_namespaces: Sequence[str] = ()) -> Context:
        ctx = cls(strip_namespaces=[ns.rstrip(".") for ns in strip_namespaces if ns.strip(".")])
        for obj in objects:
            if obj.kind in (L.KIND_GVL, L.KIND_PVL):
                ctx.gvl_names.add(obj.name.lower())
                consts: dict[str, int] = {}
                for block in L.parse_var_blocks(obj.decl):
                    if "CONSTANT" not in block.modifiers:
                        continue
                    for decl in block.decls:
                        value = parse_int_literal(decl.init_text or "")
                        if value is not None:
                            for name in decl.name_list:
                                consts[name.lower()] = value
                ctx.gvl_int_constants[obj.name.lower()] = consts
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
        return ctx


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
    """INT(0..100) -> INT."""
    for k in range(len(sig) - 1):
        if not tokens[sig[k]].is_ident(*_INT_TYPES) or not tokens[sig[k + 1]].is_op("("):
            continue
        close = _matching(tokens, sig, k + 1)
        if close > 0 and any(tokens[sig[j]].is_op("..") for j in range(k + 2, close)):
            ed.replace(sig[k + 1], sig[close], "")


def pass_array_star(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """ARRAY[*] -> ARRAY[0..0] (массив переменной длины)."""
    for k in range(len(sig) - 1):
        if not tokens[sig[k]].is_ident("ARRAY") or not tokens[sig[k + 1]].is_op("["):
            continue
        close = _matching(tokens, sig, k + 1)
        for j in range(k + 2, close if close > 0 else k + 2):
            if tokens[sig[j]].is_op("*"):
                ed.replace(sig[j], sig[j], "0..0")


def pass_lower_types(text: str, tokens: list[Token], sig: list[int], ed: Edits, ctx: Context) -> None:
    """DUT: EXTENDS у структур убирается, массивы в структурах -> тип элемента,
    базовый тип перечисления убирается."""
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
            of_index = next((i for i in range(first, last + 1) if tokens[i].is_ident("OF")), None)
            if of_index is None or of_index >= last:
                continue
            element = L.squash_ws(L.strip_comments(ed.source(of_index + 1, last)))
            ed.replace(first, last, element)
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
    for decl in decls:
        if decl.assign_index is None or decl.init_range is None:
            continue
        a = pos_of[decl.init_range[0]]
        b = pos_of[decl.init_range[1]]
        if _is_literal(tokens, sig, a, b):
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
    pass_union_to_struct,
    pass_lower_types,
    pass_drop_nonliteral_inits,
    pass_case_labels,
    pass_string_literals,
    pass_underscore_idents,
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
