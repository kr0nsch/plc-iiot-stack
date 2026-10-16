pBits := ADR(rValue);
F_IsFiniteReal := (pBits^ AND GVL_Const.REAL_EXP_MASK) <> GVL_Const.REAL_EXP_MASK;
