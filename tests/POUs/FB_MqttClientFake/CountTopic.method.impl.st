FOR uiIdx := 1 TO uiPubCount DO
    IF aPub[uiIdx].sTopic = sTopic THEN
        CountTopic := CountTopic + 1;
    END_IF
END_FOR
