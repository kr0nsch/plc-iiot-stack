pBits := ADR(lrValue);
F_IsFiniteLreal := (pBits^ AND GVL_Const.LREAL_EXP_MASK) <> GVL_Const.LREAL_EXP_MASK;
