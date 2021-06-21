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

## In order to use this project...
- Open a Binance account, enable Futures, and transfert USDT funds on it.
- Make sure your Futures account is set with margin crossed and dual-side position mode (Hedge mode) activated.
- Configure all the settings listed in the config.py file.


## Local install

Install all dependencies
``` sh
poetry install
```

## Usage

To run the algorithm on your computer, run
``` sh
make run-local
```

To run it and write the files in a bucket, run
``` sh
make run-bucket
```

## Deploy

First, add your GCP project ID, service account and bucket in Makefile.
``` Makefile
GCP_PROJECT_ID="<YOUR_PROJECT_ID>"
GCP_SERVICE_ACCOUNT="<YOUR_SERVICE_ACCOUNT>"
GCP_BUCKET="<YOUR_BUCKET>"
GCP_REGION="<LOCATION>"
SCHEDULE="0 */1 * * *"
```
Make sure the *SCHEDULE* parameter respects the cron syntax and that it corresponds to the *TIMEFRAME* set in the config.py file.

Then run
``` sh
make deploy
```
