uiSubscribeCalls := uiSubscribeCalls + 1;
sLastFilter := sTopicFilter;
eLastFilterQos := eQos;
Subscribe := xSubscribeAccepts AND IsConnected();
