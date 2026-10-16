CASE iResult OF
    1:
        F_IiotCmdResultText := 'Accepted';
    2:
        F_IiotCmdResultText := 'RejectedMode';
    3:
        F_IiotCmdResultText := 'RejectedInterlock';
    4:
        F_IiotCmdResultText := 'RejectedPermit';
    5:
        F_IiotCmdResultText := 'RejectedInhibit';
    6:
        F_IiotCmdResultText := 'RejectedFault';
    7:
        F_IiotCmdResultText := 'RejectedState';
    8:
        F_IiotCmdResultText := 'RejectedNotSupported';
    9:
        F_IiotCmdResultText := 'RejectedCfg';
ELSE
    F_IiotCmdResultText := '';
END_CASE
