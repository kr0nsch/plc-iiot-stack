// Числа: ведущий ноль, точка без цифр, знак без цифр, порядок без цифр, вне REAL, много цифр.
METHOD PRIVATE ValidatesNumberGrammarAndRange
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    lrNum : LREAL;
END_VAR
