IF liNumber < 0 THEN
    AppendByte(bChar := GVL_Const.ASCII_MINUS);
    // -(x + 1) не переполняется и для минимального LINT
    uliMagnitude := LINT_TO_ULINT(-(liNumber + 1)) + 1;
ELSE
    uliMagnitude := LINT_TO_ULINT(liNumber);
END_IF
AppendUlint(uliNumber := uliMagnitude);
