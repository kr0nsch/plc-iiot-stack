// Переполнение буфера: xOverflow, Finish = FALSE, длина не больше буфера.
METHOD PRIVATE OverflowIsReportedNotTruncatedSilently
VAR_INST
    fbJson : FB_JsonBuilder;
END_VAR
VAR
    iField : INT;
END_VAR
