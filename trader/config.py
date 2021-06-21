# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import os
from pathlib import Path
from pathy import Pathy

from trader import env

if env.is_local():
    root = Path(os.getcwd())
    root = root.parent if root.name != 'SSX999_HEDGE' else root
    
    keys_path = root / 'keys'
    public_key_path = keys_path / 'API_Public_Key'
    private_key_path = keys_path / 'API_Private_Key'

    measurements_path = root / 'measurements'
    order_ledger_path = measurements_path / 'order_ledger.csv'
    trade_ledger_path = measurements_path / 'trade_ledger.csv'
    balance_path = measurements_path / 'account_balance.csv'
    TradedCurrency_path = measurements_path / 'TradedCurrency.pickle'

else:
    gcs_bucket = env.get_var('GCP_BUCKET')
    bucket_dir = Pathy(f'gs://{gcs_bucket}')

    keys_path = Pathy('keys')
    public_key_path = keys_path / 'API_Public_Key'
    private_key_path = keys_path / 'API_Private_Key'

    measurements_path = Pathy('measurements')
    order_ledger_path = measurements_path / 'order_ledger.csv'
    trade_ledger_path = measurements_path / 'trade_ledger.csv'
    balance_path = measurements_path / 'account_balance.csv'
    TradedCurrency_path = measurements_path / 'TradedCurrency.pickle'

# ****************** START OF PARAMETERS TO SET ****************** #
BASE = 'BTC'
QUOTE = 'USDT'
PAIR = BASE + QUOTE
BASE_AMOUNT_PRECISION = 3
BASE_PRICE_PRECISION = 2
TIMEFRAME = '1h'
TIMEDELTA = '1H'
CAPITAL = 100

LEVERAGE = 100
STOP_LOSS = 0.007
TAKE_PROFIT = 0.03
REAL_MODE = False # True will perform the strategy on Binance

FAST_PERIOD = 4
SLOW_PERIOD = 10
# ******************* END OF PARAMETERS TO SET ******************* #


# ******************** DO NOT MODIFY ******************** #
CSV_SEP = ','
ORDER_LEDGER_COLUMNS = [
    'orderId', 'symbol', 'status',  'clientOrderId',
    'price', 'avgPrice', 'origQty', 'executedQty', 
    'cumQuote', 'timeInForce', 'type', 'reduceOnly', 
    'closePosition', 'side', 'positionSide', 'stopPrice', 
    'workingType', 'priceProtect', 'origType', 'time',
    'updateTime'
]
TRADE_LEDGER_COLUMNS = [
    'entry time', 'exit time', 'id',
    'entry', 'exit', 'qty',
    'leverage', 'stop loss',
    'take profit', 'actualised'
]
ACCOUNT_BALANCE_COLUMNS = [
    'accountAlias', 'asset',
    'balance', 'crossWalletBalance',
    'crossUnPnl', 'availableBalance',
    'maxWithdrawAmount', 'marginAvailable',
    'updateTime'
]
OHLC_COLUMNS = [
    'open_time',
    'open_price',
    'high_price',
    'low_price',
    'close_price',
    'volume',
    'close_time',
    'quote_volume',
    'number_of_trades',
    'taker_buy_volume',
    'taker_buy_quote_volume',
]