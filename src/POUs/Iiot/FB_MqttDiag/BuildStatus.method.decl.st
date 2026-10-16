// JSON состояния узла в fbJson: online/birth (с source, sw_version, period_ms) или offline/<sReason>.
METHOD PRIVATE BuildStatus : BOOL
VAR_INPUT
    xOnline : BOOL;
    sReason : STRING(GVL_Const.IIOT_TEXT_LEN);
END_VAR
