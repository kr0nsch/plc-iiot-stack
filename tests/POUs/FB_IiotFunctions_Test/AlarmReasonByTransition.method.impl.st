coUnit.TEST('AlarmReasonByTransition');

AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.Normal, eNew := E_IiotAlarmState.ActiveUnack)
                        = E_IiotAlarmReason.Activated, Message := 'Normal -> ActiveUnack');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.ActiveUnack, eNew := E_IiotAlarmState.ActiveAck)
                        = E_IiotAlarmReason.Acked, Message := 'ActiveUnack -> ActiveAck');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.Normal, eNew := E_IiotAlarmState.ActiveAck)
                        = E_IiotAlarmReason.Activated, Message := 'Normal -> ActiveAck');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.ActiveAck, eNew := E_IiotAlarmState.Normal)
                        = E_IiotAlarmReason.Cleared, Message := 'ActiveAck -> Normal');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.ActiveUnack, eNew := E_IiotAlarmState.RtnUnack)
                        = E_IiotAlarmReason.Cleared, Message := 'ActiveUnack -> RtnUnack');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.RtnUnack, eNew := E_IiotAlarmState.Normal)
                        = E_IiotAlarmReason.Acked, Message := 'RtnUnack -> Normal');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.ActiveAck, eNew := E_IiotAlarmState.Shelved)
                        = E_IiotAlarmReason.Shelved, Message := 'to Shelved');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.Shelved, eNew := E_IiotAlarmState.Normal)
                        = E_IiotAlarmReason.Unshelved, Message := 'from Shelved');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.Normal, eNew := E_IiotAlarmState.OutOfService)
                        = E_IiotAlarmReason.OosOn, Message := 'to OutOfService');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.OutOfService, eNew := E_IiotAlarmState.Normal)
                        = E_IiotAlarmReason.OosOff, Message := 'from OutOfService');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.Normal, eNew := E_IiotAlarmState.Normal)
                        = E_IiotAlarmReason.Cleared, Message := 'snapshot Normal');
AssertTrue(Condition := F_IiotAlarmReason(ePrev := E_IiotAlarmState.ActiveUnack, eNew := E_IiotAlarmState.ActiveUnack)
                        = E_IiotAlarmReason.Activated, Message := 'snapshot ActiveUnack');
AssertEquals_STRING(Expected := 'RtnUnack', Actual := F_IiotAlarmStateText(eState := E_IiotAlarmState.RtnUnack),
                    Message := 'state text');
AssertEquals_STRING(Expected := 'OosOff', Actual := F_IiotAlarmReasonText(eReason := E_IiotAlarmReason.OosOff),
                    Message := 'reason text');
AssertEquals_STRING(Expected := 'Critical',
    Actual := F_IiotAlarmPriorityText(ePriority := E_IiotAlarmPriority.Critical),
                    Message := 'priority text');
AssertEquals_STRING(Expected := '', Actual := F_IiotAlarmPriorityText(ePriority := E_IiotAlarmPriority.None),
                    Message := 'priority None is not published');

coUnit.TEST_FINISHED();
