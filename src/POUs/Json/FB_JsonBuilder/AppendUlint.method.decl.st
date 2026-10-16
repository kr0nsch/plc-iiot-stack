// Дописать десятичную запись целого без знака.
METHOD PRIVATE AppendUlint
VAR_INPUT
    uliNumber : ULINT;
END_VAR
VAR
    aDigits : ARRAY[0..GVL_Const.ULINT_DIGITS_MAX - 1] OF BYTE;   // цифры с младшей
    uiCount : UINT;
    uliRest : ULINT;
END_VAR
