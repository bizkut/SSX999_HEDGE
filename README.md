# SSX999_HEDGE

## Introduction

The SSX999_HEDGE project consists of an algorithm which trades Futures contracts on the Binance cryptocurrency exchange. 
The strategy is based on the possibility to open and hold opposite positions (LONG & SHORT) at the same time on the same contract. This is a very specific ability that is not made available by default on most cryptocurrency exchanges. 

Therefore, Binance was chosen for four reasons:
- It offers a powerful and maintained API enabling algorithmic trading.
- Binance's fees are among the lowest charged among exchanges at the moment.
- Binance allows to hold dual side positions through activating *hedge mode* on the Futures account.
- Markets for perpetual Futures contracts on Binance are among the most stable ones among cryptocurrency exchange.

## Description of the strategy

The strategy uses EMA crossovers to produce *action signals*. Whether the fast EMA crosses above or under the slow EMA, the resulting action is the same: open both long and short positions with the same quantity of asset, the same price and symetric stop loss and take profit levels. From this on, the market will necessarly reach either the long or the short stop loss. When that happens, the stop loss of the remaining position is adjusted to the stop loss which activated. The final stage of the life of a trade is for the remaining position to either reach the take profit initially defined, or to fall down to the updated stop loss.

While both positions are active, no profit or loss is made because each position compensate the other one. When on position is closed because the market reached its stop loss, the remaining stop loss is adjusted so that the remaining position cannot fall into loss zone. Therefore, each trade is either a break-even, either a winning trade.

Potential losses come from fees that are charged by the platform (ie: Binance), or differences between the long and short entry prices. However the lifetime of a contract averages 6 hours. Hence, the majority of contracts will not be charged daily fees (happening after holding a 2 day long contract). Besides, the differences of entry prices is estimated to be around 0.001% which is small enough to be neglected as a first development phase.

## Results

The simulation mode provided extremely good results. That is because fees and unaccuracy in prices when conditionnal orders activate are not taken into the account. As the vast majority of trades results in break-even trades, the algorithm spends a lot of money paying fees while not earning as much through winned trades. It would be tremendously profitable if a mean of sorting false signals could be discovered. Otherwise for now, the theory is exceptionnal but in reality the strategy remains a loosing one. An Excel file of the theoretical results (no fees, conditionnal orders activated at exact prices) describes the results obtained over a month or so, when rela_mode is set to False.

## In order to use this project...

This trading algorithm enables two modes. The chosen mode can be set in the config.py file by setting real_mode to either True or False. If real_mode is set to True, the algorithm will perform real trades, that is with the money available on your Binance Futures account. If it is set to False, it will simulate the trades and your money will never be traded.

*Important note: you, and only you, are responsible of the gains or losses you could encounter. I, the author of this project, cannot be taken responsible for that.*

If you wish to launch the algorithm : 
- Open a Binance account, enable Futures, (and transfert USDT funds on it if real_mode is set to True).
- Make sure your Futures account is set with margin crossed and dual-side position mode (Hedge mode) activated (if real_mode is set to True).
- Configure all the settings listed in the config.py file.

## Deploy

First, add your GCP project ID, service account and bucket in Makefile.
``` Makefile
GCP_PROJECT_ID="<YOUR_PROJECT_ID>"
GCP_SERVICE_ACCOUNT="<YOUR_SERVICE_ACCOUNT>"
GCP_BUCKET="<YOUR_BUCKET>"
GCP_REGION="<LOCATION>"
```

Then run
``` sh
make deploy
```
