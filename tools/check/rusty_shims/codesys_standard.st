(*
    Прокладки CODESYS Standard для проверки RuSTy (только объявления, не для CODESYS).

    У счётчиков CODESYS Standard другие имена входов и типы, чем в стандартной
    библиотеке RuSTy (RuSTy: CU, R, PV : INT; CODESYS: CU, RESET, PV : WORD).
    Вариант сборки rusty заменяет в объявлениях CTU/CTD/CTUD на CDS_CTU/CDS_CTD/CDS_CTUD.
    Сигнатуры CODESYS — сверить с источником: справка CODESYS, библиотека Standard
    (раздел Counter), версия, подключённая в проекте.
*)

FUNCTION_BLOCK CDS_CTU
VAR_INPUT
    CU : BOOL;
    RESET : BOOL;
    PV : WORD;
END_VAR
VAR_OUTPUT
    Q : BOOL;
    CV : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK CDS_CTD
VAR_INPUT
    CD : BOOL;
    LOAD : BOOL;
    PV : WORD;
END_VAR
VAR_OUTPUT
    Q : BOOL;
    CV : WORD;
END_VAR
END_FUNCTION_BLOCK

FUNCTION_BLOCK CDS_CTUD
VAR_INPUT
    CU : BOOL;
    CD : BOOL;
    RESET : BOOL;
    LOAD : BOOL;
    PV : WORD;
END_VAR
VAR_OUTPUT
    QU : BOOL;
    QD : BOOL;
    CV : WORD;
END_VAR
END_FUNCTION_BLOCK
