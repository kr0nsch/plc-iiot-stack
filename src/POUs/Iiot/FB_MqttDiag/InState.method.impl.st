IF ltNow < ltStateSince THEN
    ltStateSince := ltNow;
END_IF
InState := ltNow - ltStateSince;
