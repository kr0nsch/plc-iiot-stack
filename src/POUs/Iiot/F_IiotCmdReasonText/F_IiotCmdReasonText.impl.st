CASE eReason OF
    E_IiotCmdReason.Ok:
        F_IiotCmdReasonText := 'ok';
    E_IiotCmdReason.NotWhitelisted:
        F_IiotCmdReasonText := 'not_whitelisted';
    E_IiotCmdReason.OutOfRange:
        F_IiotCmdReasonText := 'out_of_range';
    E_IiotCmdReason.InvalidPayload:
        F_IiotCmdReasonText := 'invalid_payload';
    E_IiotCmdReason.UnsupportedVersion:
        F_IiotCmdReasonText := 'unsupported_version';
    E_IiotCmdReason.TopicMismatch:
        F_IiotCmdReasonText := 'topic_mismatch';
    E_IiotCmdReason.Retained:
        F_IiotCmdReasonText := 'retained';
    E_IiotCmdReason.Expired:
        F_IiotCmdReasonText := 'expired';
    E_IiotCmdReason.Duplicate:
        F_IiotCmdReasonText := 'duplicate';
    E_IiotCmdReason.RateLimited:
        F_IiotCmdReasonText := 'rate_limited';
    E_IiotCmdReason.DeviceRejected:
        F_IiotCmdReasonText := 'device_rejected';
ELSE
    F_IiotCmdReasonText := 'timeout';
END_CASE
