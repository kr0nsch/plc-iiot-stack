coUnit.TEST('NotFiniteBecomesNull');

pBits := ADR(lwNan);
lrNan := pBits^;
pBits := ADR(lwInf);
lrInf := pBits^;
fbJson.Begin();
fbJson.AddReal(sKey := 'nan', lrValue := lrNan, uiDecimals := 3);
fbJson.AddReal(sKey := 'inf', lrValue := lrInf, uiDecimals := 3);
fbJson.AddReal(sKey := 'big', lrValue := 1.0E20, uiDecimals := 3);
fbJson.Finish();
AssertEquals_STRING(Expected := '{"nan":null,"inf":null,"big":null}', Actual := fbJson.sJson,
                    Message := 'non-finite and too large numbers must be null');

coUnit.TEST_FINISHED();
