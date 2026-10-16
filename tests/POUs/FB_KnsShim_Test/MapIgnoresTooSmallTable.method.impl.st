coUnit.TEST('MapIgnoresTooSmallTable');

aSmallPoints[1].lrValue := -1.0;
aSmallPoints[1].eQuality := E_IiotQuality.Uncertain;
aSmallWords[1].wActive := 16#FFFF;
aShiftedPoints[2].lrValue := -1.0;
fbMap.FillPoints(aPointTable := aSmallPoints);
fbMap.FillAlarmWords(aWordTable := aSmallWords);
fbMap.FillPoints(aPointTable := aShiftedPoints);
AssertEquals_LREAL(Expected := -1.0, Actual := aSmallPoints[1].lrValue, Delta := 0.0,
                   Message := 'small points: value kept');
AssertTrue(Condition := aSmallPoints[1].eQuality = E_IiotQuality.Uncertain, Message := 'small points: quality kept');
AssertEquals_WORD(Expected := 16#FFFF, Actual := aSmallWords[1].wActive, Message := 'small words: kept');
AssertEquals_LREAL(Expected := -1.0, Actual := aShiftedPoints[2].lrValue, Delta := 0.0,
                   Message := 'array from 2: not filled');

coUnit.TEST_FINISHED();
