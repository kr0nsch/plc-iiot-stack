// 1. retained
IF xRxRetained THEN
    Check := E_IiotCmdReason.Retained;
    RETURN;
END_IF
// 2. состав и типы полей (command.schema.json; диапазон value — в п. 6)
Check := E_IiotCmdReason.InvalidPayload;
IF NOT fbParser.GetString(sKey := 'schema_version', sValue := sText) THEN
    RETURN;
END_IF
iMajor := F_IiotSchemaMajor(sVersion := sText);
IF iMajor < 0 THEN
    RETURN;
END_IF
FOR uiIdx := 1 TO fbParser.uiCount DO
    sKey := fbParser.KeyAt(uiIdx := uiIdx);
    IF sKey <> 'schema_version' AND sKey <> 'cmd_id' AND sKey <> 'ts' AND sKey <> 'origin' AND sKey <> 'command'
       AND sKey <> 'value' THEN
        RETURN;                     // лишнее поле: схема команды строгая
    END_IF
END_FOR
IF NOT fbParser.FieldIsInteger(sKey := 'ts') OR NOT fbParser.GetNumber(sKey := 'ts', lrValue := lrTs) THEN
    RETURN;
END_IF
IF lrTs < ULINT_TO_LREAL(GVL_Const.TS_MIN_MS) OR lrTs > ULINT_TO_LREAL(GVL_Const.TS_MAX_MS) THEN
    RETURN;
END_IF
IF NOT fbParser.GetString(sKey := 'origin', sValue := sText) THEN
    RETURN;
END_IF
IF NOT F_IiotIsPrintable(sText := sText, iMaxLen := UINT_TO_INT(GVL_Const.CMD_ORIGIN_LEN)) THEN
    RETURN;
END_IF
IF NOT fbParser.GetString(sKey := 'command', sValue := sText) THEN
    RETURN;
END_IF
eCommand := F_IiotCmdFromString(sCommand := sText);
IF eCommand = E_IiotCommand.None THEN
    RETURN;
END_IF
eKind := F_IiotCmdKind(eCommand := eCommand);
xHasValue := fbParser.FieldType(sKey := 'value') <> E_JsonType.Missing;
IF xHasValue AND NOT fbParser.GetNumber(sKey := 'value', lrValue := lrValue) THEN
    RETURN;                         // value не число
END_IF
IF eKind = E_IiotCmdKind.Pulse AND xHasValue THEN
    RETURN;                         // value у импульсной команды
END_IF
IF eKind <> E_IiotCmdKind.Pulse AND NOT xHasValue THEN
    RETURN;                         // нет value
END_IF
IF eKind = E_IiotCmdKind.Mask
   AND (NOT fbParser.FieldIsInteger(sKey := 'value') OR lrValue < 0.0 OR lrValue > GVL_Const.CMD_MASK_MAX) THEN
    RETURN;                         // маска: целое 0..65535
END_IF
// 3. мажорная версия
IF iMajor <> UINT_TO_INT(GVL_Const.IIOT_SCHEMA_MAJOR) THEN
    Check := E_IiotCmdReason.UnsupportedVersion;
    RETURN;
END_IF
// 4. команда в теле и в топике
IF sText <> sTopicCommand THEN
    Check := E_IiotCmdReason.TopicMismatch;
    RETURN;
END_IF
// 5. белый список
diRule := FindRule(aRuleTable := aRuleTable, eCommandIn := eCommand);
IF diRule < LOWER_BOUND(aRuleTable, 1) THEN
    Check := E_IiotCmdReason.NotWhitelisted;
    RETURN;
END_IF
// 6. диапазон значения
IF xHasValue THEN
    IF aRuleTable[diRule].xRange THEN
        lrMin := REAL_TO_LREAL(aRuleTable[diRule].rMin);
        lrMax := REAL_TO_LREAL(aRuleTable[diRule].rMax);
    ELSE
        lrMin := -GVL_Const.REAL_ABS_MAX;
        lrMax := GVL_Const.REAL_ABS_MAX;
    END_IF
    IF eCommand = E_IiotCommand.SpeedSp THEN       // схема: 0..100 % независимо от белого списка
        lrMin := MAX(lrMin, GVL_Const.SPEED_SP_MIN_PCT);
        lrMax := MIN(lrMax, GVL_Const.SPEED_SP_MAX_PCT);
    END_IF
    IF lrValue < lrMin OR lrValue > lrMax THEN
        Check := E_IiotCmdReason.OutOfRange;
        RETURN;
    END_IF
END_IF
// 7. возраст ts (часы ПЛК должны быть установлены)
IF NOT F_IiotClockValid(uliTs_ms := uliTs_ms)
   OR ABS(ULINT_TO_LREAL(uliTs_ms) - lrTs) > ULINT_TO_LREAL(TIME_TO_ULINT(tMaxAge)) THEN
    Check := E_IiotCmdReason.Expired;
    RETURN;
END_IF
// 8. повтор cmd_id
IF IsDuplicate() THEN
    Check := E_IiotCmdReason.Duplicate;
    RETURN;
END_IF
// 9. частота
IF NOT RateAllows() THEN
    Check := E_IiotCmdReason.RateLimited;
    RETURN;
END_IF
stCmd.diRule := diRule;
stCmd.sDevice := sTopicDevice;
stCmd.sCommand := sTopicCommand;
stCmd.eCommand := eCommand;
stCmd.rValue := LREAL_TO_REAL(lrValue);
stCmd.sCmdId := sCmdId;
Check := E_IiotCmdReason.Ok;
