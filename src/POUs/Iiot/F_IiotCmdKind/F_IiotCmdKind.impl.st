CASE eCommand OF
    E_IiotCommand.SpeedSp, E_IiotCommand.SubstValue:
        F_IiotCmdKind := E_IiotCmdKind.Value;
    E_IiotCommand.AckReq, E_IiotCommand.ShelveReq, E_IiotCommand.UnshelveReq:
        F_IiotCmdKind := E_IiotCmdKind.Mask;
ELSE
    F_IiotCmdKind := E_IiotCmdKind.Pulse;
END_CASE
