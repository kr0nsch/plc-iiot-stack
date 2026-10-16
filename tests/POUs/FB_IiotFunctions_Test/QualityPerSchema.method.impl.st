coUnit.TEST('QualityPerSchema');

AssertTrue(Condition := F_IiotQuality(xValid := TRUE, iNe107 := 0) = E_IiotQuality.Good, Message := 'Good, valid');
AssertTrue(Condition := F_IiotQuality(xValid := TRUE, iNe107 := 1) = E_IiotQuality.Good, Message := 'M, valid');
AssertTrue(Condition := F_IiotQuality(xValid := FALSE, iNe107 := 1) = E_IiotQuality.Bad, Message := 'M, invalid');
AssertTrue(Condition := F_IiotQuality(xValid := TRUE, iNe107 := 2) = E_IiotQuality.Uncertain, Message := 'S');
AssertTrue(Condition := F_IiotQuality(xValid := FALSE, iNe107 := 3) = E_IiotQuality.Uncertain, Message := 'C, invalid');
AssertTrue(Condition := F_IiotQuality(xValid := TRUE, iNe107 := 4) = E_IiotQuality.Bad, Message := 'F');
AssertTrue(Condition := F_IiotQuality(xValid := FALSE, iNe107 := 0) = E_IiotQuality.Bad, Message := 'Good, invalid');
AssertEquals_STRING(Expected := 'uncertain', Actual := F_IiotQualityText(eQuality := E_IiotQuality.Uncertain),
                    Message := 'quality text');

coUnit.TEST_FINISHED();
