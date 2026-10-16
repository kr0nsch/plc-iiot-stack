IF bDigit >= GVL_Const.ASCII_ZERO AND bDigit <= GVL_Const.ASCII_NINE THEN
    HexValue := BYTE_TO_INT(bDigit - GVL_Const.ASCII_ZERO);
ELSIF bDigit >= GVL_Const.ASCII_LOWER_A AND bDigit <= GVL_Const.ASCII_LOWER_F THEN
    HexValue := BYTE_TO_INT(bDigit - GVL_Const.ASCII_LOWER_A + GVL_Const.HEX_LETTER_START);
ELSIF bDigit >= GVL_Const.ASCII_UPPER_A AND bDigit <= GVL_Const.ASCII_UPPER_F THEN
    HexValue := BYTE_TO_INT(bDigit - GVL_Const.ASCII_UPPER_A + GVL_Const.HEX_LETTER_START);
ELSE
    HexValue := -1;
END_IF
