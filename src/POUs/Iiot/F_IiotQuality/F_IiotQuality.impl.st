IF iNe107 >= TO_INT(E_IiotNe107.Failure) THEN
    F_IiotQuality := E_IiotQuality.Bad;
ELSIF iNe107 = TO_INT(E_IiotNe107.OutOfSpecification) OR iNe107 = TO_INT(E_IiotNe107.CheckFunction) THEN
    F_IiotQuality := E_IiotQuality.Uncertain;
ELSIF xValid THEN
    F_IiotQuality := E_IiotQuality.Good;
ELSE
    F_IiotQuality := E_IiotQuality.Bad;
END_IF
