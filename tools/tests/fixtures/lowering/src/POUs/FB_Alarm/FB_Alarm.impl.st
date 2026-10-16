// Системное время, длительности с пропуском единиц, пустые операторы и ветви
IF xOn THEN
    tStamp := TIME();
    ltStamp := LTIME();
ELSIF tStamp > t#5s THEN
    ;
ELSE
    // состояние не меняется
END_IF
if tStamp >= T#1h_30m then
    tStamp := tLimit;
end_if;;
