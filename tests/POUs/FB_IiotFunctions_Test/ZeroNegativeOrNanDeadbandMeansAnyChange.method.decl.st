// Зона <= 0 или не число — любое изменение.
METHOD PRIVATE ZeroNegativeOrNanDeadbandMeansAnyChange
VAR
    dwNan : DWORD := 16#7FC00000;
    pBitsR : POINTER TO REAL;
    rNan : REAL;
END_VAR
