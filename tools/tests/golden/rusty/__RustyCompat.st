(* Вспомогательная функция совместимости для проверки RuSTy (не для CODESYS):
   проверка, что интерфейсная переменная задана (itfX <> 0 в CODESYS). *)
FUNCTION __ItfIsSet : BOOL
VAR_INPUT
    pFat : POINTER TO LWORD;
END_VAR
__ItfIsSet := pFat^ <> 0;
END_FUNCTION
