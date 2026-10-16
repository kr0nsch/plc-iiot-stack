fbJson.Begin();
fbJson.AddString(sKey := 'schema_version', sValue := GVL_Const.IIOT_SCHEMA_VERSION);
fbJson.AddInt(sKey := 'ts', liValue := ULINT_TO_LINT(uliTs_ms));
fbJson.AddString(sKey := 'node', sValue := sNode);
IF xOnline THEN
    fbJson.AddString(sKey := 'state', sValue := 'online');
ELSE
    fbJson.AddString(sKey := 'state', sValue := 'offline');
END_IF
fbJson.AddString(sKey := 'reason', sValue := sReason);
IF xOnline THEN
    fbJson.AddString(sKey := 'source', sValue := GVL_Const.IIOT_SOURCE);
    fbJson.AddString(sKey := 'sw_version', sValue := sSwVersion);
    fbJson.AddInt(sKey := 'period_ms', liValue := ULINT_TO_LINT(TIME_TO_ULINT(tPeriod)));
END_IF
BuildStatus := fbJson.Finish();
