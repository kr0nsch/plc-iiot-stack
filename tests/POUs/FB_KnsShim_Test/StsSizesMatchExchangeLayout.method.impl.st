coUnit.TEST('StsSizesMatchExchangeLayout');

AssertEquals_UDINT(Expected := 28, Actual := SIZEOF(ST_DeviceSts), Message := 'ST_DeviceSts 28 bytes');
AssertEquals_UDINT(Expected := 44, Actual := SIZEOF(ST_AnalogInputSts), Message := 'ST_AnalogInputSts 44 bytes');
AssertEquals_UDINT(Expected := 30, Actual := SIZEOF(ST_DigitalInputSts), Message := 'ST_DigitalInputSts 30 bytes');
AssertEquals_UDINT(Expected := 68, Actual := SIZEOF(ST_MotorSts), Message := 'ST_MotorSts 68 bytes');

coUnit.TEST_FINISHED();
