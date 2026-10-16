// Объект ровно на размер буфера — полный, на байт больше — переполнение.
METHOD PRIVATE BufferHoldsExactlyItsSize
VAR_INST
    fbJson : FB_JsonBuilder;
END_VAR
VAR
    iField : INT;
END_VAR
