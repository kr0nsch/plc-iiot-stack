IF xNeedComma THEN
    AppendByte(bChar := GVL_Const.ASCII_COMMA);
END_IF
xNeedComma := TRUE;
AppendByte(bChar := GVL_Const.ASCII_QUOTE);
AppendEscaped(sText := sKeyName);
AppendByte(bChar := GVL_Const.ASCII_QUOTE);
AppendByte(bChar := GVL_Const.ASCII_COLON);
