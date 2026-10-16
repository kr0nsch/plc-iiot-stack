bDigit := bNibble AND GVL_Const.NIBBLE_MASK;
IF bDigit < GVL_Const.HEX_LETTER_START THEN
    AppendByte(bChar := GVL_Const.ASCII_ZERO + bDigit);
ELSE
    AppendByte(bChar := GVL_Const.ASCII_LOWER_A + (bDigit - GVL_Const.HEX_LETTER_START));
END_IF
