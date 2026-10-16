coUnit.TEST('DegradedWhenPublishFailuresGrow');

fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tDegradeWindow := T#10S, udiPubFailed := 0,
       stBroker := stCfg);
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#10S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tDegradeWindow := T#10S, udiPubFailed := 3,
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.xDegraded AND fbDiag.eNe107 = E_IiotNe107.MaintenanceRequired,
    Message := 'M on failures');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#20S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tDegradeWindow := T#10S, udiPubFailed := 3,
       stBroker := stCfg);

AssertTrue(Condition := NOT fbDiag.xDegraded AND fbDiag.eNe107 = E_IiotNe107.Good,
    Message := 'Good without new failures');

coUnit.TEST_FINISHED();
