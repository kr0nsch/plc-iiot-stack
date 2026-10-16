IF NOT IsConnected() OR NOT xPublishAccepts THEN
    uiPubRejected := uiPubRejected + 1;
    RETURN;
END_IF
Publish := TRUE;
uiPubTotal := uiPubTotal + 1;
IF NOT Captured(sTopicIn := sTopic) OR uiPubCount >= PUB_MAX THEN
    RETURN;
END_IF
uiPubCount := uiPubCount + 1;
aPub[uiPubCount].sTopic := sTopic;
aPub[uiPubCount].sPayload := sPayload;
aPub[uiPubCount].eQos := eQos;
aPub[uiPubCount].xRetain := xRetain;
