IF NOT IsConnected() THEN
    RETURN;
END_IF
sSubFilter := sTopicFilter;
eSubQos := ToLibQos(eQosIn := eQos);
xSubscribe := TRUE;
Subscribe := NOT fbSubscriber.SubscribeFail;
