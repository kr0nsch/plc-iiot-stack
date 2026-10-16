# -*- coding: utf-8 -*-
"""Разбор и запись раскладки исходников ST по контракту docs/LAYOUT.md.

Единственная реализация контракта раскладки. Модуль импортируют и скрипты CODESYS
(IronPython 2.7), и инструменты на Python 3, поэтому он написан на общем подмножестве
Python 2.7 и 3.8+: без f-строк, аннотаций типов (только комментарии типов), pathlib,
dataclasses; файлы читаются и пишутся через io.open(..., encoding='utf-8').

Состав:
- нормализация текста: normalize_text();
- лексер ST без потерь: tokenize(), significant_indices(), strip_comments();
- разбор объявлений: parse_header(), parse_var_blocks(), parse_type_decl();
- модель объектов: StObject, StMethod, StProperty;
- обход раскладки и проверки: scan() -> ScanResult (объекты и замечания LayoutIssue);
- запись раскладки (для экспорта): object_files(), write_objects().

Нормализация текста (normalize_text): убирается BOM, CRLF и одиночный CR заменяются на LF,
у каждой строки срезаются хвостовые пробелы и табы, хвостовые пустые строки убираются,
непустой текст завершается ровно одним переводом строки, текст из одних пробельных
символов превращается в пустую строку. Табы в начале и середине строки не трогаются.
"""

from __future__ import absolute_import, print_function, unicode_literals

import io
import os
import re

MYPY = False
if MYPY:  # pragma: no cover - только для mypy
    from typing import Dict, List, Optional, Sequence, Tuple  # noqa: F401

__all__ = [
    "CATEGORIES",
    "KIND_DUT",
    "KIND_GVL",
    "KIND_ITF",
    "KIND_POU",
    "KIND_PVL",
    "POU_FUNCTION",
    "POU_FUNCTION_BLOCK",
    "POU_PROGRAM",
    "DeclHeader",
    "LayoutIssue",
    "ScanResult",
    "StMethod",
    "StObject",
    "StProperty",
    "Token",
    "TypeDecl",
    "VarBlock",
    "VarDecl",
    "case_label_indices",
    "normalize_text",
    "object_files",
    "parse_header",
    "parse_type_decl",
    "parse_var_blocks",
    "read_text",
    "scan",
    "significant_indices",
    "squash_ws",
    "strip_comments",
    "tokenize",
    "write_objects",
    "write_text",
]

# ---------------------------------------------------------------------------
# Константы раскладки
# ---------------------------------------------------------------------------

KIND_DUT = "dut"
KIND_GVL = "gvl"
KIND_PVL = "pvl"
KIND_ITF = "itf"
KIND_POU = "pou"

POU_PROGRAM = "program"
POU_FUNCTION_BLOCK = "function_block"
POU_FUNCTION = "function"

CAT_DUTS = "DUTs"
CAT_GVLS = "GVLs"
CAT_ITFS = "Interfaces"
CAT_POUS = "POUs"
CATEGORIES = (CAT_DUTS, CAT_GVLS, CAT_ITFS, CAT_POUS)

SUFFIX_DUT = ".dut.st"
SUFFIX_GVL = ".gvl.st"
SUFFIX_PVL = ".pvl.st"
SUFFIX_ITF = ".itf.st"
SUFFIX_DECL = ".decl.st"
SUFFIX_IMPL = ".impl.st"
SUFFIX_METHOD_DECL = ".method.decl.st"
SUFFIX_METHOD_IMPL = ".method.impl.st"
SUFFIX_PROP_DECL = ".prop.decl.st"
SUFFIX_GET_DECL = ".get.decl.st"
SUFFIX_GET_IMPL = ".get.impl.st"
SUFFIX_SET_DECL = ".set.decl.st"
SUFFIX_SET_IMPL = ".set.impl.st"

_CATEGORY_OF_KIND = {
    KIND_DUT: CAT_DUTS,
    KIND_GVL: CAT_GVLS,
    KIND_PVL: CAT_GVLS,
    KIND_ITF: CAT_ITFS,
    KIND_POU: CAT_POUS,
}
_FLAT_SUFFIX_OF_KIND = {KIND_DUT: SUFFIX_DUT, KIND_GVL: SUFFIX_GVL, KIND_PVL: SUFFIX_PVL}
_POU_KIND_OF_KEYWORD = {
    "PROGRAM": POU_PROGRAM,
    "FUNCTION_BLOCK": POU_FUNCTION_BLOCK,
    "FUNCTION": POU_FUNCTION,
}
_END_OF_POU_KIND = {
    POU_PROGRAM: "END_PROGRAM",
    POU_FUNCTION_BLOCK: "END_FUNCTION_BLOCK",
    POU_FUNCTION: "END_FUNCTION",
}

# Коды замечаний раскладки (см. tools/README.md)
LAY_UNKNOWN_FILE = "LAY001"
LAY_NAME_MISMATCH = "LAY002"
LAY_MISSING_FILE = "LAY003"
LAY_ORPHAN_FILE = "LAY004"
LAY_BAD_CONTENT = "LAY005"
LAY_DUPLICATE = "LAY006"
LAY_ENCODING = "LAY007"
LAY_MISPLACED = "LAY008"
LAY_BAD_HEADER = "LAY009"
LAY_BAD_NAME = "LAY010"

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

# ---------------------------------------------------------------------------
# Текст: нормализация, чтение, запись
# ---------------------------------------------------------------------------

_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def normalize_text(text):
    # type: (str) -> str
    """Нормализует текст исходника (правила — в документации модуля)."""
    text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS_RE.sub("", text)
    text = text.rstrip("\n")
    if not text.strip():
        return ""
    return text + "\n"


def read_text(path):
    # type: (str) -> str
    """Читает файл как UTF-8 без преобразования переводов строк (BOM сохраняется)."""
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _makedirs(path):
    # type: (str) -> None
    if path and not os.path.isdir(path):
        os.makedirs(path)


def write_text(path, text):
    # type: (str, str) -> None
    """Записывает текст в UTF-8 без BOM, переводы строк — как в тексте (LF)."""
    _makedirs(os.path.dirname(path))
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def squash_ws(text):
    # type: (str) -> str
    """Схлопывает любые пробельные последовательности в один пробел."""
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Лексер ST (без потерь: конкатенация текстов токенов равна исходному тексту)
# ---------------------------------------------------------------------------

TK_WS = "ws"
TK_COMMENT = "comment"
TK_PRAGMA = "pragma"
TK_IDENT = "ident"
TK_NUMBER = "number"
TK_TYPED = "typed"
TK_STRING = "string"
TK_WSTRING = "wstring"
TK_OP = "op"
TK_ADDRESS = "address"
TK_OTHER = "other"

_TRIVIA = (TK_WS, TK_COMMENT, TK_PRAGMA)

_WS_RE = re.compile(r"[ \t\r\n\f\v]+")
_IDENT_RE = re.compile(r"[^\W\d]\w*", re.UNICODE)
_NUM_RE = re.compile(r"[0-9][0-9_]*(?:#[0-9A-Fa-f_]+|(?:\.[0-9][0-9_]*)?(?:[eE][-+]?[0-9][0-9_]*)?)")
_TIME_VALUE_RE = re.compile(r"[-+]?[0-9A-Za-z_.]+")
_DATE_VALUE_RE = re.compile(r"[-+]?[0-9A-Za-z_.:]+(?:-[0-9A-Za-z_.:]+)*")
_TYPED_VALUE_RE = re.compile(r"[-+]?[0-9A-Za-z_#]+(?:\.[0-9A-Za-z_]+)?(?:[eE][-+]?[0-9]+)?")
_ADDRESS_RE = re.compile(r"%[IQMiqm][XBWDLxbwdl]?(?:\*|[0-9]+(?:\.[0-9]+)*)?")
_COMMENT_MARK_RE = re.compile(r"\(\*|\*\)")
_OPS2 = (":=", "=>", "<>", "<=", ">=", "**", "..", "?=")
_OPS1 = "+-*/=<>()[],;:.^&#@?!|~"
_TIME_PREFIXES = ("T", "TIME", "LT", "LTIME")
_DATE_PREFIXES = ("D", "DATE", "LD", "LDATE", "DT", "DATE_AND_TIME", "LDT", "TOD", "TIME_OF_DAY", "LTOD")


class Token(object):
    """Токен ST: вид, текст, смещение в тексте, строка и столбец (с 1)."""

    __slots__ = ("col", "kind", "line", "pos", "text")

    def __init__(self, kind, text, pos, line, col):
        # type: (str, str, int, int, int) -> None
        self.kind = kind
        self.text = text
        self.pos = pos
        self.line = line
        self.col = col

    @property
    def upper(self):
        # type: () -> str
        return self.text.upper()

    @property
    def end(self):
        # type: () -> int
        return self.pos + len(self.text)

    def is_ident(self, *words):
        # type: (*str) -> bool
        """Идентификатор (без учёта регистра); без аргументов — любой идентификатор."""
        if self.kind != TK_IDENT:
            return False
        return not words or self.text.upper() in words

    def is_op(self, *ops):
        # type: (*str) -> bool
        return self.kind == TK_OP and (not ops or self.text in ops)

    def __repr__(self):
        # type: () -> str
        return "Token(%s, %r, line=%d, col=%d)" % (self.kind, self.text, self.line, self.col)


def _scan_block_comment(text, pos):
    # type: (str, int) -> int
    depth = 0
    i = pos
    while True:
        match = _COMMENT_MARK_RE.search(text, i)
        if match is None:
            return len(text)
        if match.group(0) == "(*":
            depth += 1
        else:
            depth -= 1
        i = match.end()
        if depth == 0:
            return i


def _scan_string(text, pos, quote):
    # type: (str, int, str) -> int
    i = pos + 1
    n = len(text)
    while i < n:
        char = text[i]
        if char == "$":
            i += 2
            continue
        if char == quote:
            return i + 1
        if char == "\n" or char == "\r":
            return i
        i += 1
    return n


def tokenize(text):
    # type: (str) -> List[Token]
    """Разбивает текст ST на токены без потерь (включая пробелы, комментарии, прагмы).

    Комментарии: //..., (* ... *) с вложенностью, /* ... */. Прагмы: {...}.
    Строки: '...' (STRING) и "..." (WSTRING) с экранированием через $.
    Типизированные литералы (T#5s, INT#3, E_Mode#Auto, DT#...) — один токен 'typed'.
    """
    tokens = []  # type: List[Token]
    pos = 0
    line = 1
    col = 1
    n = len(text)
    while pos < n:
        char = text[pos]
        kind = TK_OTHER
        end = pos + 1
        if char in " \t\r\n\f\v":
            match = _WS_RE.match(text, pos)
            end = match.end() if match else pos + 1
            kind = TK_WS
        elif text.startswith("//", pos):
            end = pos + 2
            while end < n and text[end] not in "\r\n":
                end += 1
            kind = TK_COMMENT
        elif text.startswith("(*", pos):
            end = _scan_block_comment(text, pos)
            kind = TK_COMMENT
        elif text.startswith("/*", pos):
            found = text.find("*/", pos + 2)
            end = n if found < 0 else found + 2
            kind = TK_COMMENT
        elif char == "{":
            found = text.find("}", pos + 1)
            end = n if found < 0 else found + 1
            kind = TK_PRAGMA
        elif char == "'" or char == '"':
            end = _scan_string(text, pos, char)
            kind = TK_STRING if char == "'" else TK_WSTRING
        elif "0" <= char <= "9":
            match = _NUM_RE.match(text, pos)
            end = match.end() if match else pos + 1
            kind = TK_NUMBER
        elif char == "%":
            match = _ADDRESS_RE.match(text, pos)
            if match and match.end() > pos + 2:
                end = match.end()
                kind = TK_ADDRESS
            else:
                kind = TK_OP
        else:
            match = _IDENT_RE.match(text, pos)
            if match:
                end = match.end()
                kind = TK_IDENT
                if end < n and text[end] == "#":
                    prefix = text[pos:end].upper()
                    if prefix in _TIME_PREFIXES:
                        value_re = _TIME_VALUE_RE
                    elif prefix in _DATE_PREFIXES:
                        value_re = _DATE_VALUE_RE
                    else:
                        value_re = _TYPED_VALUE_RE
                    value = value_re.match(text, end + 1)
                    if value:
                        end = value.end()
                        kind = TK_TYPED
            elif text[pos : pos + 2] in _OPS2:
                end = pos + 2
                kind = TK_OP
            elif char in _OPS1:
                kind = TK_OP
        piece = text[pos:end]
        tokens.append(Token(kind, piece, pos, line, col))
        newlines = piece.count("\n")
        if newlines:
            line += newlines
            col = len(piece) - piece.rfind("\n")
        else:
            col += len(piece)
        pos = end
    return tokens


def significant_indices(tokens):
    # type: (Sequence[Token]) -> List[int]
    """Индексы значимых токенов (без пробелов, комментариев и прагм)."""
    return [i for i, tok in enumerate(tokens) if tok.kind not in _TRIVIA]


def strip_comments(text, pragmas=True):
    # type: (str, bool) -> str
    """Заменяет комментарии (и прагмы) пробелами, сохраняя переводы строк и позиции."""
    out = []
    for tok in tokenize(text):
        if tok.kind == TK_COMMENT or (pragmas and tok.kind == TK_PRAGMA):
            out.append(re.sub(r"[^\n]", " ", tok.text))
        else:
            out.append(tok.text)
    return "".join(out)


# ---------------------------------------------------------------------------
# Разбор объявлений
# ---------------------------------------------------------------------------

HEADER_KEYWORDS = (
    "TYPE",
    "VAR_GLOBAL",
    "INTERFACE",
    "PROGRAM",
    "FUNCTION_BLOCK",
    "FUNCTION",
    "METHOD",
    "PROPERTY",
)
MODIFIER_KEYWORDS = ("PUBLIC", "PRIVATE", "PROTECTED", "INTERNAL", "ABSTRACT", "FINAL")
VAR_SECTION_KEYWORDS = (
    "VAR",
    "VAR_INPUT",
    "VAR_OUTPUT",
    "VAR_IN_OUT",
    "VAR_GLOBAL",
    "VAR_TEMP",
    "VAR_STAT",
    "VAR_INST",
    "VAR_EXTERNAL",
    "VAR_CONFIG",
    "VAR_ACCESS",
)
VAR_MODIFIERS = ("CONSTANT", "RETAIN", "PERSISTENT", "NON_RETAIN")


class DeclHeader(object):
    """Заголовок объявления: ключевое слово, имя, модификаторы, наследование, тип."""

    def __init__(self, keyword, keyword_index, line):
        # type: (str, int, int) -> None
        self.keyword = keyword  # PROGRAM, FUNCTION_BLOCK, TYPE, ...
        self.keyword_index = keyword_index  # индекс токена ключевого слова
        self.line = line  # строка имени (или ключевого слова, если имени нет)
        self.name = None  # type: Optional[str]
        self.name_index = None  # type: Optional[int]
        self.modifiers = []  # type: List[str]
        self.extends = []  # type: List[str]
        self.implements = []  # type: List[str]
        self.return_type = None  # type: Optional[str]
        # индексы первого и последнего токена типа результата (включительно)
        self.return_type_range = None  # type: Optional[Tuple[int, int]]
        self.type_kind = None  # type: Optional[str]  # struct, union, enum, alias (для TYPE)
        # индексы токенов EXTENDS/IMPLEMENTS с их списками: (первый, последний)
        self.extends_range = None  # type: Optional[Tuple[int, int]]
        self.implements_range = None  # type: Optional[Tuple[int, int]]
        self.modifier_indices = []  # type: List[int]

    def __repr__(self):
        # type: () -> str
        return "DeclHeader(%s %s)" % (self.keyword, self.name)


class _Cursor(object):
    """Курсор по значимым токенам."""

    def __init__(self, tokens, sig, k=0):
        # type: (Sequence[Token], List[int], int) -> None
        self.tokens = tokens
        self.sig = sig
        self.k = k

    def peek(self, offset=0):
        # type: (int) -> Optional[Token]
        j = self.k + offset
        if 0 <= j < len(self.sig):
            return self.tokens[self.sig[j]]
        return None

    def index(self, offset=0):
        # type: (int) -> int
        j = self.k + offset
        if 0 <= j < len(self.sig):
            return self.sig[j]
        return len(self.tokens)

    def at_end(self):
        # type: () -> bool
        return self.k >= len(self.sig)


def _qualified_name(cur):
    # type: (_Cursor) -> Optional[str]
    tok = cur.peek()
    if tok is None or tok.kind != TK_IDENT:
        return None
    parts = [tok.text]
    cur.k += 1
    while True:
        dot = cur.peek()
        nxt = cur.peek(1)
        if dot is not None and dot.is_op(".") and nxt is not None and nxt.kind == TK_IDENT:
            parts.append(nxt.text)
            cur.k += 2
        else:
            break
    return ".".join(parts)


def _qualified_list(cur):
    # type: (_Cursor) -> List[str]
    names = []  # type: List[str]
    while True:
        name = _qualified_name(cur)
        if name is None:
            break
        names.append(name)
        tok = cur.peek()
        if tok is not None and tok.is_op(","):
            cur.k += 1
            continue
        break
    return names


def _range_text(text, tokens, first, last):
    # type: (str, Sequence[Token], int, int) -> str
    return squash_ws(strip_comments(text[tokens[first].pos : tokens[last].end]))


def parse_header(text, tokens=None):
    # type: (str, Optional[List[Token]]) -> Optional[DeclHeader]
    """Разбирает заголовок объявления, пропуская комментарии и прагмы.

    Возвращает DeclHeader или None, если первый значимый токен — не ключевое слово
    объявления (TYPE, VAR_GLOBAL, INTERFACE, PROGRAM, FUNCTION_BLOCK, FUNCTION,
    METHOD, PROPERTY).
    """
    if tokens is None:
        tokens = tokenize(text)
    sig = significant_indices(tokens)
    if not sig:
        return None
    first = tokens[sig[0]]
    if not first.is_ident(*HEADER_KEYWORDS):
        return None
    keyword = first.upper
    hdr = DeclHeader(keyword, sig[0], first.line)
    cur = _Cursor(tokens, sig, 1)
    if keyword == "VAR_GLOBAL":
        while True:
            tok = cur.peek()
            if tok is None or not tok.is_ident(*VAR_MODIFIERS):
                break
            hdr.modifiers.append(tok.upper)
            hdr.modifier_indices.append(cur.index())
            cur.k += 1
        return hdr
    while True:
        tok = cur.peek()
        if tok is None or not tok.is_ident(*MODIFIER_KEYWORDS):
            break
        hdr.modifiers.append(tok.upper)
        hdr.modifier_indices.append(cur.index())
        cur.k += 1
    tok = cur.peek()
    if tok is None or tok.kind != TK_IDENT:
        return hdr
    hdr.name = tok.text
    hdr.name_index = cur.index()
    hdr.line = tok.line
    cur.k += 1
    if keyword == "TYPE":
        _parse_type_tail(text, tokens, cur, hdr)
        return hdr
    if keyword in ("INTERFACE", "FUNCTION_BLOCK"):
        while True:
            tok = cur.peek()
            if tok is not None and tok.is_ident("EXTENDS"):
                start = cur.index()
                cur.k += 1
                hdr.extends.extend(_qualified_list(cur))
                hdr.extends_range = (start, cur.index(-1))
            elif tok is not None and tok.is_ident("IMPLEMENTS"):
                start = cur.index()
                cur.k += 1
                hdr.implements.extend(_qualified_list(cur))
                hdr.implements_range = (start, cur.index(-1))
            else:
                break
        return hdr
    if keyword in ("FUNCTION", "METHOD", "PROPERTY"):
        colon = cur.peek()
        if colon is not None and colon.is_op(":"):
            cur.k += 1
            first_k = cur.k
            while True:
                tok = cur.peek()
                if tok is None or tok.line != colon.line or tok.is_op(";"):
                    break
                if tok.is_ident(*VAR_SECTION_KEYWORDS):
                    break
                cur.k += 1
            if cur.k > first_k:
                first_idx = sig[first_k]
                last_idx = sig[cur.k - 1]
                hdr.return_type_range = (first_idx, last_idx)
                hdr.return_type = _range_text(text, tokens, first_idx, last_idx)
    return hdr


def _parse_type_tail(text, tokens, cur, hdr):
    # type: (str, Sequence[Token], _Cursor, DeclHeader) -> None
    tok = cur.peek()
    if tok is not None and tok.is_ident("EXTENDS"):
        start = cur.index()
        cur.k += 1
        hdr.extends.extend(_qualified_list(cur))
        hdr.extends_range = (start, cur.index(-1))
    tok = cur.peek()
    if tok is None or not tok.is_op(":"):
        return
    cur.k += 1
    tok = cur.peek()
    if tok is None:
        return
    if tok.is_ident("STRUCT"):
        hdr.type_kind = "struct"
    elif tok.is_ident("UNION"):
        hdr.type_kind = "union"
    elif tok.is_op("("):
        hdr.type_kind = "enum"
    else:
        hdr.type_kind = "alias"


class VarDecl(object):
    """Объявление переменной (или поля структуры): имена, тип, начальное значение.

    Индексы — в полном списке токенов текста, из которого шёл разбор.
    """

    def __init__(self):
        # type: () -> None
        self.names = []  # type: List[Tuple[str, int]]
        self.address_index = None  # type: Optional[int]
        self.colon_index = None  # type: Optional[int]
        self.type_range = None  # type: Optional[Tuple[int, int]]
        self.type_text = ""
        self.assign_index = None  # type: Optional[int]
        self.init_range = None  # type: Optional[Tuple[int, int]]
        self.init_text = None  # type: Optional[str]
        self.semi_index = None  # type: Optional[int]
        self.first_index = 0
        self.last_index = 0
        self.line = 0
        self.section = ""  # VAR, VAR_INPUT, ..., STRUCT
        self.modifiers = []  # type: List[str]

    @property
    def name_list(self):
        # type: () -> List[str]
        return [name for name, _ in self.names]

    def __repr__(self):
        # type: () -> str
        return "VarDecl(%s : %s)" % (", ".join(self.name_list), self.type_text)


class VarBlock(object):
    """Секция VAR... END_VAR."""

    def __init__(self, keyword, keyword_index):
        # type: (str, int) -> None
        self.keyword = keyword
        self.keyword_index = keyword_index
        self.modifiers = []  # type: List[str]
        self.modifier_indices = []  # type: List[int]
        self.end_index = None  # type: Optional[int]
        self.decls = []  # type: List[VarDecl]


def _build_decl(text, tokens, sig, start, stop, section, modifiers):
    # type: (str, Sequence[Token], List[int], int, int, str, List[str]) -> Optional[VarDecl]
    if stop <= start:
        return None
    decl = VarDecl()
    decl.section = section
    decl.modifiers = list(modifiers)
    decl.first_index = sig[start]
    decl.last_index = sig[stop - 1]
    k = start
    while k < stop:
        tok = tokens[sig[k]]
        if tok.kind != TK_IDENT:
            break
        decl.names.append((tok.text, sig[k]))
        k += 1
        if k < stop and tokens[sig[k]].is_op(","):
            k += 1
            continue
        break
    if not decl.names:
        return None
    decl.line = tokens[decl.names[0][1]].line
    if k < stop and tokens[sig[k]].is_ident("AT"):
        k += 1
        if k < stop:
            decl.address_index = sig[k]
            k += 1
    if k >= stop or not tokens[sig[k]].is_op(":"):
        return decl
    decl.colon_index = sig[k]
    k += 1
    type_first = k
    depth = 0
    while k < stop:
        tok = tokens[sig[k]]
        if tok.is_op("(", "["):
            depth += 1
        elif tok.is_op(")", "]"):
            depth -= 1
        elif tok.is_op(":=") and depth <= 0:
            break
        k += 1
    if k > type_first:
        decl.type_range = (sig[type_first], sig[k - 1])
        decl.type_text = _range_text(text, tokens, sig[type_first], sig[k - 1])
    if k < stop and tokens[sig[k]].is_op(":="):
        decl.assign_index = sig[k]
        if stop > k + 1:
            decl.init_range = (sig[k + 1], sig[stop - 1])
            decl.init_text = _range_text(text, tokens, sig[k + 1], sig[stop - 1])
    return decl


def _parse_decl_list(
    text,  # type: str
    tokens,  # type: Sequence[Token]
    sig,  # type: List[int]
    k,  # type: int
    end_words,  # type: Tuple[str, ...]
    section,  # type: str
    modifiers,  # type: List[str]
):
    # type: (...) -> Tuple[List[VarDecl], int]
    decls = []  # type: List[VarDecl]
    n = len(sig)
    while k < n:
        tok = tokens[sig[k]]
        if tok.is_ident(*end_words):
            return decls, k
        start = k
        depth = 0
        while k < n:
            tok = tokens[sig[k]]
            if tok.is_op("(", "["):
                depth += 1
            elif tok.is_op(")", "]"):
                depth -= 1
            elif tok.is_op(";") and depth <= 0:
                break
            elif depth <= 0 and tok.is_ident(*end_words):
                break
            k += 1
        decl = _build_decl(text, tokens, sig, start, k, section, modifiers)
        if decl is not None:
            if k < n and tokens[sig[k]].is_op(";"):
                decl.semi_index = sig[k]
            decls.append(decl)
        if k < n and tokens[sig[k]].is_op(";"):
            k += 1
    return decls, k


def parse_var_blocks(text, tokens=None):
    # type: (str, Optional[List[Token]]) -> List[VarBlock]
    """Находит секции VAR*... END_VAR и разбирает объявления переменных в них."""
    if tokens is None:
        tokens = tokenize(text)
    sig = significant_indices(tokens)
    blocks = []  # type: List[VarBlock]
    k = 0
    n = len(sig)
    while k < n:
        tok = tokens[sig[k]]
        if not tok.is_ident(*VAR_SECTION_KEYWORDS):
            k += 1
            continue
        block = VarBlock(tok.upper, sig[k])
        k += 1
        while k < n and tokens[sig[k]].is_ident(*VAR_MODIFIERS):
            block.modifiers.append(tokens[sig[k]].upper)
            block.modifier_indices.append(sig[k])
            k += 1
        block.decls, k = _parse_decl_list(text, tokens, sig, k, ("END_VAR",), block.keyword, block.modifiers)
        if k < n:
            block.end_index = sig[k]
            k += 1
        blocks.append(block)
    return blocks


class TypeDecl(object):
    """Разобранный DUT: вид, поля структуры/объединения, значения перечисления."""

    def __init__(self, header):
        # type: (DeclHeader) -> None
        self.header = header
        self.kind = header.type_kind  # struct, union, enum, alias
        self.members = []  # type: List[VarDecl]
        self.body_start_index = None  # type: Optional[int]  # STRUCT/UNION или '('
        self.body_end_index = None  # type: Optional[int]  # END_STRUCT/END_UNION или ')'
        # значения перечисления: (имя, текст значения или None, индекс токена имени)
        self.enum_values = []  # type: List[Tuple[str, Optional[str], int]]
        self.enum_base_range = None  # type: Optional[Tuple[int, int]]
        self.enum_base_type = None  # type: Optional[str]
        self.alias_type = None  # type: Optional[str]


def parse_type_decl(text, tokens=None):
    # type: (str, Optional[List[Token]]) -> Optional[TypeDecl]
    """Разбирает текст DUT (TYPE ... END_TYPE). None — если это не TYPE."""
    if tokens is None:
        tokens = tokenize(text)
    hdr = parse_header(text, tokens)
    if hdr is None or hdr.keyword != "TYPE":
        return None
    result = TypeDecl(hdr)
    sig = significant_indices(tokens)
    n = len(sig)
    k = 0
    # позиция после ':' заголовка
    while k < n and not tokens[sig[k]].is_op(":"):
        k += 1
    k += 1
    if k >= n:
        return result
    if result.kind in ("struct", "union"):
        end_word = "END_STRUCT" if result.kind == "struct" else "END_UNION"
        result.body_start_index = sig[k]
        result.members, k = _parse_decl_list(text, tokens, sig, k + 1, (end_word, "END_TYPE"), result.kind.upper(), [])
        if k < n and tokens[sig[k]].is_ident(end_word):
            result.body_end_index = sig[k]
    elif result.kind == "enum":
        result.body_start_index = sig[k]
        k += 1
        depth = 1
        item_start = k
        items = []  # type: List[Tuple[int, int]]
        while k < n:
            tok = tokens[sig[k]]
            if tok.is_op("(", "["):
                depth += 1
            elif tok.is_op(")", "]"):
                depth -= 1
                if depth == 0:
                    items.append((item_start, k))
                    break
            elif tok.is_op(",") and depth == 1:
                items.append((item_start, k))
                item_start = k + 1
            k += 1
        if k < n:
            result.body_end_index = sig[k]
        for a, b in items:
            if a >= b or tokens[sig[a]].kind != TK_IDENT:
                continue
            value = None  # type: Optional[str]
            if a + 1 < b and tokens[sig[a + 1]].is_op(":="):
                if a + 2 < b:
                    value = _range_text(text, tokens, sig[a + 2], sig[b - 1])
            result.enum_values.append((tokens[sig[a]].text, value, sig[a]))
        k += 1
        base_first = k
        while k < n and not tokens[sig[k]].is_op(";", ":=") and not tokens[sig[k]].is_ident("END_TYPE"):
            k += 1
        if k > base_first:
            result.enum_base_range = (sig[base_first], sig[k - 1])
            result.enum_base_type = _range_text(text, tokens, sig[base_first], sig[k - 1])
    else:
        first = k
        while k < n and not tokens[sig[k]].is_op(";", ":=") and not tokens[sig[k]].is_ident("END_TYPE"):
            k += 1
        if k > first:
            result.alias_type = _range_text(text, tokens, sig[first], sig[k - 1])
    return result


def _find_ident(tokens, words):
    # type: (Sequence[Token], Tuple[str, ...]) -> Optional[Token]
    for tok in tokens:
        if tok.is_ident(*words):
            return tok
    return None


# Токены, после которых в теле CASE может начинаться метка (CODESYS допускает END_IF без ';')
_LABEL_PRECEDERS = ("OF", "END_IF", "END_CASE", "END_FOR", "END_WHILE", "END_REPEAT")


def _match_label_list(tokens, sig, k):
    # type: (Sequence[Token], List[int], int) -> int
    """Если с позиции k идёт список меток CASE и ':', возвращает позицию ':', иначе -1."""
    n = len(sig)
    j = k
    while True:
        for _ in range(2):  # значение или диапазон значение..значение
            if j < n and tokens[sig[j]].is_op("-", "+"):
                j += 1
            if j >= n:
                return -1
            tok = tokens[sig[j]]
            if tok.kind in (TK_NUMBER, TK_TYPED):
                j += 1
            elif tok.kind == TK_IDENT and tok.upper not in ("ELSE", "END_CASE"):
                j += 1
                while j + 1 < n and tokens[sig[j]].is_op(".") and tokens[sig[j + 1]].kind == TK_IDENT:
                    j += 2
            else:
                return -1
            if j < n and tokens[sig[j]].is_op(".."):
                j += 1
                continue
            break
        if j >= n:
            return -1
        tok = tokens[sig[j]]
        if tok.is_op(","):
            j += 1
            continue
        if tok.is_op(":"):
            return j
        return -1


def case_label_indices(tokens, sig=None):
    # type: (Sequence[Token], Optional[List[int]]) -> List[int]
    """Индексы (в полном списке) значимых токенов, из которых состоят метки CASE."""
    if sig is None:
        sig = significant_indices(tokens)
    labels = []  # type: List[int]
    depth = 0
    k = 0
    n = len(sig)
    while k < n:
        tok = tokens[sig[k]]
        if tok.is_ident("CASE"):
            depth += 1
        elif tok.is_ident("END_CASE"):
            depth = max(0, depth - 1)
        elif depth > 0 and k > 0:
            prev = tokens[sig[k - 1]]
            if prev.is_op(";") or prev.is_ident(*_LABEL_PRECEDERS):
                colon = _match_label_list(tokens, sig, k)
                if colon > 0:
                    labels.extend(sig[k:colon])
                    k = colon + 1
                    continue
        k += 1
    return labels


# ---------------------------------------------------------------------------
# Модель объектов
# ---------------------------------------------------------------------------


class StMethod(object):
    """Метод POU или интерфейса. У метода интерфейса impl = None."""

    def __init__(self, name, decl, impl=None):
        # type: (str, str, Optional[str]) -> None
        self.name = name
        self.decl = decl
        self.impl = impl
        self.header = None  # type: Optional[DeclHeader]

    @property
    def is_abstract(self):
        # type: () -> bool
        hdr = self.header or parse_header(self.decl)
        return hdr is not None and "ABSTRACT" in hdr.modifiers

    def __repr__(self):
        # type: () -> str
        return "StMethod(%s)" % self.name


class StProperty(object):
    """Свойство. Аксессор существует, если есть его decl или impl (не None)."""

    def __init__(self, name, decl, get_decl=None, get_impl=None, set_decl=None, set_impl=None):
        # type: (str, str, Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        self.name = name
        self.decl = decl
        self.get_decl = get_decl
        self.get_impl = get_impl
        self.set_decl = set_decl
        self.set_impl = set_impl
        self.header = None  # type: Optional[DeclHeader]

    @property
    def has_get(self):
        # type: () -> bool
        return self.get_decl is not None or self.get_impl is not None

    @property
    def has_set(self):
        # type: () -> bool
        return self.set_decl is not None or self.set_impl is not None

    def __repr__(self):
        # type: () -> str
        return "StProperty(%s)" % self.name


class StObject(object):
    """Объект CODESYS из раскладки.

    kind: dut, gvl, pvl, itf, pou; pou_kind (для pou): program, function_block, function.
    folder: список папок проекта CODESYS внутри категории (DUTs/GVLs/Interfaces/POUs).
    decl: полный текст файла DUT/GVL/PVL, объявление интерфейса или POU.
    impl: тело POU (None для остальных или если файла нет).
    subdir: корневой каталог раскладки (src, tests).
    """

    def __init__(self, kind, name, decl, folder=None, impl=None, pou_kind=None, subdir="src"):
        # type: (str, str, str, Optional[List[str]], Optional[str], Optional[str], str) -> None
        self.kind = kind
        self.name = name
        self.decl = decl
        self.folder = list(folder or [])
        self.impl = impl
        self.pou_kind = pou_kind
        self.subdir = subdir
        self.methods = []  # type: List[StMethod]
        self.properties = []  # type: List[StProperty]
        self.header = None  # type: Optional[DeclHeader]

    @property
    def category(self):
        # type: () -> str
        return _CATEGORY_OF_KIND[self.kind]

    @property
    def extends(self):
        # type: () -> List[str]
        return list(self.header.extends) if self.header else []

    @property
    def implements(self):
        # type: () -> List[str]
        return list(self.header.implements) if self.header else []

    def rel_dir(self, subdir=None):
        # type: (Optional[str]) -> str
        """Каталог объекта (интерфейс, POU) или папки (DUT, GVL) относительно корня."""
        parts = [subdir or self.subdir, self.category] + self.folder
        if self.kind in (KIND_ITF, KIND_POU):
            parts.append(self.name)
        return "/".join(parts)

    def main_path(self, subdir=None):
        # type: (Optional[str]) -> str
        """Путь главного файла объекта относительно корня (posix)."""
        return object_files(self, subdir)[0][0]

    def sorted_members(self):
        # type: () -> None
        self.methods.sort(key=lambda m: (m.name.lower(), m.name))
        self.properties.sort(key=lambda p: (p.name.lower(), p.name))

    def __repr__(self):
        # type: () -> str
        return "StObject(%s %s)" % (self.pou_kind or self.kind, self.name)


class LayoutIssue(object):
    """Замечание к раскладке: код LAYxxx, путь (posix, от корня), строка, текст."""

    def __init__(self, code, path, line, message, severity="error"):
        # type: (str, str, int, str, str) -> None
        self.code = code
        self.path = path
        self.line = line
        self.message = message
        self.severity = severity

    def format(self):
        # type: () -> str
        return "%s:%d: %s %s" % (self.path, self.line, self.code, self.message)

    def __repr__(self):
        # type: () -> str
        return "LayoutIssue(%s)" % self.format()


class ScanResult(object):
    """Результат обхода: объекты в детерминированном порядке и замечания."""

    def __init__(self):
        # type: () -> None
        self.objects = []  # type: List[StObject]
        self.issues = []  # type: List[LayoutIssue]

    @property
    def errors(self):
        # type: () -> List[LayoutIssue]
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self):
        # type: () -> bool
        return not self.errors

    def find(self, name):
        # type: (str) -> Optional[StObject]
        for obj in self.objects:
            if obj.name.lower() == name.lower():
                return obj
        return None

    def add(self, code, path, line, message, severity="error"):
        # type: (str, str, int, str, str) -> None
        self.issues.append(LayoutIssue(code, path, line, message, severity))


# ---------------------------------------------------------------------------
# Обход раскладки
# ---------------------------------------------------------------------------


def _is_ignored(name):
    # type: (str) -> bool
    """Скрытые файлы и каталоги (.gitkeep, ...) и *.md в раскладке игнорируются."""
    return name.startswith(".") or name.lower().endswith(".md")


def _listdir(path):
    # type: (str) -> List[str]
    return sorted(os.listdir(path), key=lambda n: (n.lower(), n))


def _split_name(filename):
    # type: (str) -> Tuple[str, str]
    dot = filename.find(".")
    if dot < 0:
        return filename, ""
    return filename[:dot], filename[dot:]


def _join(*parts):
    # type: (*str) -> str
    return "/".join(p for p in parts if p)


class _Reader(object):
    def __init__(self, root, result):
        # type: (str, ScanResult) -> None
        self.root = root
        self.result = result

    def read(self, rel):
        # type: (str) -> Optional[str]
        path = os.path.join(self.root, *rel.split("/"))
        try:
            raw = read_text(path)
        except UnicodeDecodeError as exc:
            self.result.add(LAY_ENCODING, rel, 1, "файл не в кодировке UTF-8: %s" % exc)
            return None
        return normalize_text(raw)


def _check_name(result, rel, name):
    # type: (ScanResult, str, str) -> bool
    if _NAME_RE.match(name):
        return True
    result.add(LAY_BAD_NAME, rel, 1, "имя '%s' — не идентификатор ST (ASCII, буквы, цифры, _)" % name)
    return False


def _check_header(result, rel, text, keywords, expected_name, what):
    # type: (ScanResult, str, str, Tuple[str, ...], Optional[str], str) -> Optional[DeclHeader]
    tokens = tokenize(text)
    hdr = parse_header(text, tokens)
    if hdr is None or hdr.keyword not in keywords:
        line = hdr.line if hdr is not None else 1
        result.add(LAY_BAD_HEADER, rel, line, "ожидалось объявление %s (%s)" % (what, " / ".join(keywords)))
        return None
    if expected_name is not None:
        if hdr.name is None:
            result.add(LAY_BAD_HEADER, rel, hdr.line, "в объявлении %s нет имени" % hdr.keyword)
        elif hdr.name != expected_name:
            result.add(
                LAY_NAME_MISMATCH,
                rel,
                hdr.line,
                "имя в тексте '%s' не совпадает с именем файла '%s'" % (hdr.name, expected_name),
            )
    return hdr


def _check_no_end(result, rel, text, words, what):
    # type: (ScanResult, str, str, Tuple[str, ...], str) -> None
    tok = _find_ident(tokenize(text), words)
    if tok is not None:
        result.add(LAY_BAD_CONTENT, rel, tok.line, "%s: %s в раскладке не пишется" % (what, tok.text))


def _check_has_end(result, rel, text, word):
    # type: (ScanResult, str, str, str) -> None
    if _find_ident(tokenize(text), (word,)) is None:
        result.add(LAY_BAD_CONTENT, rel, 1, "нет %s" % word)


_IMPL_FORBIDDEN = (
    "END_PROGRAM",
    "END_FUNCTION_BLOCK",
    "END_FUNCTION",
    "END_METHOD",
    "END_PROPERTY",
    "END_INTERFACE",
)


def scan(root, subdir="src"):
    # type: (str, str) -> ScanResult
    """Обходит root/subdir по контракту docs/LAYOUT.md.

    Объекты упорядочены: категория (DUTs, GVLs, Interfaces, POUs), папки, имя
    (без учёта регистра); методы и свойства — по алфавиту. Тексты нормализованы.
    Отсутствие root/subdir — пустой результат без замечаний.
    """
    result = ScanResult()
    base = os.path.join(root, subdir)
    if not os.path.isdir(base):
        return result
    reader = _Reader(root, result)
    for entry in _listdir(base):
        if _is_ignored(entry):
            continue
        full = os.path.join(base, entry)
        if os.path.isdir(full) and entry in CATEGORIES:
            continue
        result.add(
            LAY_MISPLACED,
            _join(subdir, entry),
            1,
            "неизвестный элемент: на верхнем уровне допустимы только %s" % ", ".join(CATEGORIES),
        )
    for category in CATEGORIES:
        cat_dir = os.path.join(base, category)
        if not os.path.isdir(cat_dir):
            continue
        rel = _join(subdir, category)
        if category in (CAT_DUTS, CAT_GVLS):
            _scan_flat(reader, subdir, category, cat_dir, rel, [])
        else:
            _scan_tree(reader, subdir, category, cat_dir, rel, [])
    _check_duplicates(result)
    order = dict((cat, i) for i, cat in enumerate(CATEGORIES))
    result.objects.sort(
        key=lambda o: (
            order[o.category],
            [f.lower() for f in o.folder],
            o.folder,
            o.name.lower(),
            o.name,
        )
    )
    for obj in result.objects:
        obj.sorted_members()
    return result


def _scan_flat(reader, subdir, category, directory, rel, folder):
    # type: (_Reader, str, str, str, str, List[str]) -> None
    result = reader.result
    if category == CAT_DUTS:
        suffixes = {SUFFIX_DUT: KIND_DUT}
    else:
        suffixes = {SUFFIX_GVL: KIND_GVL, SUFFIX_PVL: KIND_PVL}
    for entry in _listdir(directory):
        if _is_ignored(entry):
            continue
        full = os.path.join(directory, entry)
        entry_rel = _join(rel, entry)
        if os.path.isdir(full):
            if _check_name(result, entry_rel, entry):
                _scan_flat(reader, subdir, category, full, entry_rel, folder + [entry])
            continue
        name, suffix = _split_name(entry)
        kind = suffixes.get(suffix)
        if kind is None:
            result.add(
                LAY_UNKNOWN_FILE,
                entry_rel,
                1,
                "неизвестный вид файла в %s (ожидается %s)" % (category, ", ".join(sorted(suffixes))),
            )
            continue
        if not _check_name(result, entry_rel, name):
            continue
        text = reader.read(entry_rel)
        if text is None:
            continue
        obj = StObject(kind, name, text, folder=folder, subdir=subdir)
        if kind == KIND_DUT:
            obj.header = _check_header(result, entry_rel, text, ("TYPE",), name, "типа")
            _check_has_end(result, entry_rel, text, "END_TYPE")
        else:
            obj.header = _check_header(result, entry_rel, text, ("VAR_GLOBAL",), None, "списка переменных")
            _check_has_end(result, entry_rel, text, "END_VAR")
            if kind == KIND_PVL and obj.header is not None and "PERSISTENT" not in obj.header.modifiers:
                result.add(
                    LAY_BAD_CONTENT,
                    entry_rel,
                    obj.header.line,
                    "в .pvl.st ожидается VAR_GLOBAL PERSISTENT",
                    severity="warning",
                )
        result.objects.append(obj)


def _scan_tree(reader, subdir, category, directory, rel, folder):
    # type: (_Reader, str, str, str, str, List[str]) -> None
    result = reader.result
    main_suffix = SUFFIX_ITF if category == CAT_ITFS else SUFFIX_DECL
    for entry in _listdir(directory):
        if _is_ignored(entry):
            continue
        full = os.path.join(directory, entry)
        entry_rel = _join(rel, entry)
        if not os.path.isdir(full):
            result.add(
                LAY_MISPLACED,
                entry_rel,
                1,
                "файл вне каталога объекта: в %s файлы лежат в <Имя>/ рядом с <Имя>%s" % (category, main_suffix),
            )
            continue
        if not _check_name(result, entry_rel, entry):
            continue
        if os.path.isfile(os.path.join(full, entry + main_suffix)):
            if category == CAT_ITFS:
                _scan_interface(reader, subdir, full, entry_rel, folder, entry)
            else:
                _scan_pou(reader, subdir, full, entry_rel, folder, entry)
        else:
            _scan_tree(reader, subdir, category, full, entry_rel, folder + [entry])


_POU_MEMBER_SUFFIXES = (
    SUFFIX_METHOD_DECL,
    SUFFIX_METHOD_IMPL,
    SUFFIX_PROP_DECL,
    SUFFIX_GET_DECL,
    SUFFIX_GET_IMPL,
    SUFFIX_SET_DECL,
    SUFFIX_SET_IMPL,
)
_ITF_MEMBER_SUFFIXES = (SUFFIX_METHOD_DECL, SUFFIX_PROP_DECL, SUFFIX_GET_DECL, SUFFIX_SET_DECL)


def _collect_member_files(
    reader,  # type: _Reader
    directory,  # type: str
    rel,  # type: str
    obj_name,  # type: str
    main_suffixes,  # type: Tuple[str, ...]
    member_suffixes,  # type: Tuple[str, ...]
    what,  # type: str
):
    # type: (...) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]
    """Читает файлы каталога объекта: (главные файлы по суффиксу, члены по суффиксу и имени)."""
    result = reader.result
    mains = {}  # type: Dict[str, str]
    members = {}  # type: Dict[str, Dict[str, str]]
    all_suffixes = _POU_MEMBER_SUFFIXES + (SUFFIX_DECL, SUFFIX_IMPL, SUFFIX_ITF)
    for entry in _listdir(directory):
        if _is_ignored(entry):
            continue
        entry_rel = _join(rel, entry)
        if os.path.isdir(os.path.join(directory, entry)):
            result.add(LAY_MISPLACED, entry_rel, 1, "вложенный каталог внутри объекта %s не поддерживается" % obj_name)
            continue
        name, suffix = _split_name(entry)
        if suffix in main_suffixes and name == obj_name:
            text = reader.read(entry_rel)
            if text is not None:
                mains[suffix] = text
            continue
        if suffix in member_suffixes:
            if not _check_name(result, entry_rel, name):
                continue
            text = reader.read(entry_rel)
            if text is not None:
                members.setdefault(suffix, {})[name] = text
            continue
        if suffix in main_suffixes:
            message = "файл '%s' не относится к объекту %s" % (entry, obj_name)
        elif suffix in all_suffixes:
            message = "файл %s недопустим в %s" % (entry, what)
            if suffix.endswith(SUFFIX_IMPL):
                message += " (у интерфейса нет реализаций)"
        else:
            message = "неизвестный вид файла: %s" % entry
        result.add(LAY_UNKNOWN_FILE, entry_rel, 1, message)
    return mains, members


def _scan_interface(reader, subdir, directory, rel, folder, name):
    # type: (_Reader, str, str, str, List[str], str) -> None
    result = reader.result
    mains, members = _collect_member_files(
        reader, directory, rel, name, (SUFFIX_ITF,), _ITF_MEMBER_SUFFIXES, "интерфейсе"
    )
    if SUFFIX_ITF not in mains:
        return
    decl = mains[SUFFIX_ITF]
    main_rel = _join(rel, name + SUFFIX_ITF)
    obj = StObject(KIND_ITF, name, decl, folder=folder, subdir=subdir)
    obj.header = _check_header(result, main_rel, decl, ("INTERFACE",), name, "интерфейса")
    _check_no_end(result, main_rel, decl, ("END_INTERFACE",), "объявление интерфейса")
    for mname in sorted(members.get(SUFFIX_METHOD_DECL, {})):
        mtext = members[SUFFIX_METHOD_DECL][mname]
        mrel = _join(rel, mname + SUFFIX_METHOD_DECL)
        method = StMethod(mname, mtext)
        method.header = _check_header(result, mrel, mtext, ("METHOD",), mname, "метода")
        _check_no_end(result, mrel, mtext, ("END_METHOD",), "объявление метода")
        obj.methods.append(method)
    _collect_properties(result, rel, obj, members)
    _check_member_names(result, rel, obj)
    result.objects.append(obj)


def _scan_pou(reader, subdir, directory, rel, folder, name):
    # type: (_Reader, str, str, str, List[str], str) -> None
    result = reader.result
    mains, members = _collect_member_files(
        reader, directory, rel, name, (SUFFIX_DECL, SUFFIX_IMPL), _POU_MEMBER_SUFFIXES, "POU"
    )
    if SUFFIX_DECL not in mains:
        return
    decl = mains[SUFFIX_DECL]
    decl_rel = _join(rel, name + SUFFIX_DECL)
    impl_rel = _join(rel, name + SUFFIX_IMPL)
    obj = StObject(KIND_POU, name, decl, folder=folder, impl=mains.get(SUFFIX_IMPL), subdir=subdir)
    obj.header = _check_header(result, decl_rel, decl, ("PROGRAM", "FUNCTION_BLOCK", "FUNCTION"), name, "POU")
    if obj.header is not None:
        obj.pou_kind = _POU_KIND_OF_KEYWORD[obj.header.keyword]
    _check_no_end(result, decl_rel, decl, ("END_PROGRAM", "END_FUNCTION_BLOCK", "END_FUNCTION"), "объявление POU")
    if obj.impl is None:
        result.add(LAY_MISSING_FILE, impl_rel, 1, "нет тела POU (пустое тело — файл с комментарием)")
    else:
        _check_no_end(result, impl_rel, obj.impl, _IMPL_FORBIDDEN, "тело POU")
    mdecls = members.get(SUFFIX_METHOD_DECL, {})
    mimpls = members.get(SUFFIX_METHOD_IMPL, {})
    for mname in sorted(mimpls):
        if mname not in mdecls:
            result.add(
                LAY_ORPHAN_FILE,
                _join(rel, mname + SUFFIX_METHOD_IMPL),
                1,
                "тело метода без объявления %s%s" % (mname, SUFFIX_METHOD_DECL),
            )
    for mname in sorted(mdecls):
        mtext = mdecls[mname]
        mrel = _join(rel, mname + SUFFIX_METHOD_DECL)
        method = StMethod(mname, mtext, mimpls.get(mname))
        method.header = _check_header(result, mrel, mtext, ("METHOD",), mname, "метода")
        _check_no_end(result, mrel, mtext, ("END_METHOD",), "объявление метода")
        if method.impl is None and not method.is_abstract:
            result.add(
                LAY_MISSING_FILE,
                _join(rel, mname + SUFFIX_METHOD_IMPL),
                1,
                "нет тела метода %s (обязательно, кроме ABSTRACT)" % mname,
            )
        elif method.impl is not None:
            _check_no_end(result, _join(rel, mname + SUFFIX_METHOD_IMPL), method.impl, _IMPL_FORBIDDEN, "тело метода")
        obj.methods.append(method)
    _collect_properties(result, rel, obj, members)
    if obj.pou_kind == POU_FUNCTION and (obj.methods or obj.properties):
        result.add(LAY_BAD_CONTENT, decl_rel, 1, "у FUNCTION не может быть методов и свойств")
    _check_member_names(result, rel, obj)
    result.objects.append(obj)


def _collect_properties(result, rel, obj, members):
    # type: (ScanResult, str, StObject, Dict[str, Dict[str, str]]) -> None
    pdecls = members.get(SUFFIX_PROP_DECL, {})
    accessor_suffixes = (SUFFIX_GET_DECL, SUFFIX_GET_IMPL, SUFFIX_SET_DECL, SUFFIX_SET_IMPL)
    for suffix in accessor_suffixes:
        for pname in sorted(members.get(suffix, {})):
            if pname not in pdecls:
                result.add(
                    LAY_ORPHAN_FILE,
                    _join(rel, pname + suffix),
                    1,
                    "аксессор без объявления свойства %s%s" % (pname, SUFFIX_PROP_DECL),
                )
    for pname in sorted(pdecls):
        ptext = pdecls[pname]
        prel = _join(rel, pname + SUFFIX_PROP_DECL)
        prop = StProperty(
            pname,
            ptext,
            get_decl=members.get(SUFFIX_GET_DECL, {}).get(pname),
            get_impl=members.get(SUFFIX_GET_IMPL, {}).get(pname),
            set_decl=members.get(SUFFIX_SET_DECL, {}).get(pname),
            set_impl=members.get(SUFFIX_SET_IMPL, {}).get(pname),
        )
        prop.header = _check_header(result, prel, ptext, ("PROPERTY",), pname, "свойства")
        if prop.header is not None and prop.header.name and not prop.header.return_type:
            result.add(LAY_BAD_HEADER, prel, prop.header.line, "у свойства нет типа (PROPERTY <Имя> : <тип>)")
        _check_no_end(result, prel, ptext, ("END_PROPERTY",), "объявление свойства")
        if not prop.has_get and not prop.has_set:
            result.add(
                LAY_MISSING_FILE,
                prel,
                1,
                "у свойства нет аксессоров (%s.get.*.st / %s.set.*.st)" % (pname, pname),
            )
        for accessor_text, suffix in ((prop.get_impl, SUFFIX_GET_IMPL), (prop.set_impl, SUFFIX_SET_IMPL)):
            if accessor_text is not None:
                _check_no_end(result, _join(rel, pname + suffix), accessor_text, _IMPL_FORBIDDEN, "тело аксессора")
        obj.properties.append(prop)


def _check_member_names(result, rel, obj):
    # type: (ScanResult, str, StObject) -> None
    seen = {}  # type: Dict[str, str]
    for member in [m.name for m in obj.methods] + [p.name for p in obj.properties]:
        key = member.lower()
        if key in seen:
            result.add(
                LAY_DUPLICATE,
                rel,
                1,
                "в %s повторяется имя метода/свойства '%s' (имена CODESYS без учёта регистра)" % (obj.name, member),
            )
        seen[key] = member


def _check_duplicates(result):
    # type: (ScanResult) -> None
    seen = {}  # type: Dict[str, StObject]
    for obj in result.objects:
        key = obj.name.lower()
        if key in seen:
            result.add(
                LAY_DUPLICATE,
                obj.main_path(),
                1,
                "объект '%s' уже объявлен в %s (имена CODESYS без учёта регистра)" % (obj.name, seen[key].main_path()),
            )
        else:
            seen[key] = obj


# ---------------------------------------------------------------------------
# Запись раскладки
# ---------------------------------------------------------------------------


def object_files(obj, subdir=None):
    # type: (StObject, Optional[str]) -> List[Tuple[str, str]]
    """Файлы объекта: [(путь posix относительно корня, текст)]; первый — главный файл."""
    base = obj.rel_dir(subdir)
    if obj.kind in _FLAT_SUFFIX_OF_KIND:
        return [(_join(base, obj.name + _FLAT_SUFFIX_OF_KIND[obj.kind]), obj.decl)]
    files = []  # type: List[Tuple[str, str]]
    if obj.kind == KIND_ITF:
        files.append((_join(base, obj.name + SUFFIX_ITF), obj.decl))
    else:
        files.append((_join(base, obj.name + SUFFIX_DECL), obj.decl))
        if obj.impl is not None:
            files.append((_join(base, obj.name + SUFFIX_IMPL), obj.impl))
    for method in obj.methods:
        files.append((_join(base, method.name + SUFFIX_METHOD_DECL), method.decl))
        if method.impl is not None:
            files.append((_join(base, method.name + SUFFIX_METHOD_IMPL), method.impl))
    for prop in obj.properties:
        files.append((_join(base, prop.name + SUFFIX_PROP_DECL), prop.decl))
        for text, suffix in (
            (prop.get_decl, SUFFIX_GET_DECL),
            (prop.get_impl, SUFFIX_GET_IMPL),
            (prop.set_decl, SUFFIX_SET_DECL),
            (prop.set_impl, SUFFIX_SET_IMPL),
        ):
            if text is not None:
                files.append((_join(base, prop.name + suffix), text))
    return files


def _fix_case(root, rel):
    # type: (str, str) -> None
    """Приводит регистр уже существующих каталогов и файла пути rel к записываемому.

    Имена CODESYS не различают регистр. На файловой системе без учёта регистра (Windows)
    запись FB_Example/FB_Example.decl.st поверх fb_example/fb_example.decl.st сохранила бы
    старое имя, а clean=True затем удалил бы этот файл как «лишний» — объект пропал бы.
    Переименование — в два шага через временное имя: смена только регистра одним
    rename поддерживается не везде.
    """
    current = root
    for part in rel.split("/"):
        if os.path.isdir(current):
            names = os.listdir(current)
            if part not in names:
                for name in names:
                    if name.lower() == part.lower():
                        old = os.path.join(current, name)
                        tmp = os.path.join(current, name + ".~case")
                        os.rename(old, tmp)
                        os.rename(tmp, os.path.join(current, part))
                        break
        current = os.path.join(current, part)


def write_objects(objects, root, subdir="src", clean=False):
    # type: (Sequence[StObject], str, str, bool) -> List[str]
    """Записывает объекты в раскладку root/subdir (тексты нормализуются).

    Для нормализованного входа scan() -> write_objects() даёт побайтно те же файлы.
    Регистр имён существующих каталогов и файлов приводится к именам объектов (_fix_case).
    clean=True удаляет из root/subdir/{DUTs,GVLs,Interfaces,POUs} файлы *.st, которых
    нет среди записанных, и опустевшие каталоги (нужно экспорту, чтобы удалённые в
    проекте объекты исчезали из src/). Возвращает отсортированный список путей.
    """
    written = []  # type: List[str]
    for obj in objects:
        for rel, text in object_files(obj, subdir):
            _fix_case(root, rel)
            path = os.path.join(root, *rel.split("/"))
            write_text(path, normalize_text(text))
            written.append(rel)
    if clean:
        keep = set(written)
        base = os.path.join(root, subdir)
        for category in CATEGORIES:
            cat_dir = os.path.join(base, category)
            if not os.path.isdir(cat_dir):
                continue
            for dirpath, _dirnames, filenames in os.walk(cat_dir, topdown=False):
                for filename in filenames:
                    if not filename.endswith(".st"):
                        continue
                    full = os.path.join(dirpath, filename)
                    rel = os.path.relpath(full, root).replace(os.sep, "/")
                    if rel not in keep:
                        os.remove(full)
                if dirpath != cat_dir and not os.listdir(dirpath):
                    os.rmdir(dirpath)
    return sorted(written)
