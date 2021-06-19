# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import os
from pathlib import Path
from pathy import Pathy

import env


def get_var(key: str):
    return os.environ.get(key)


keys_path = Path('keys')
data_path = Path('historical_data')
generated_data_path = Path('generated_data')

if env.is_local():
    keys_dir = keys_path
    data_dir = data_path
    generated_data_dir = generated_data_path
else:
    gcs_bucket = get_var('GCP_BUCKET')
    bucket_dir = Pathy(f'gs://{gcs_bucket}')

    keys_dir = bucket_dir / keys_path
    data_dir = bucket_dir / data_path
    generated_data_dir = bucket_dir / generated_data_path


wallet_filename = 'wallet.pickle'
wallet_path = generated_data_dir / wallet_filename
lasts_path = generated_data_dir / 'lasts.pickle'
performances_path = generated_data_dir / 'performances.csv'

public_key =  keys_dir / 'API_Public_Key'
private_key = keys_dir / 'API_Private_Key'


QUOTE = 'EUR'
PERIOD = '4h'
CAPITAL = 100
UNIVERSE = ['ADA', 'ETH', 'BTC', 'XTZ', 'WAVES', 'EOS']
DATA_COLUMNS = ['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count']
FEE_RATE = 0.16 / 100
CSV_SEP = ','

LEVERAGE = 125
STOP_LOSS = 0.007
TAKE_PROFIT = 0.03
TIME_RANGE = '1H'
REAL_MODE = False # True will perform the strategy on Binance

TIME_FRAMES = {
    '1mn': 1,
    '5mn': 5,
    '15mn': 15,
    '30mn': 30,
    '1h': 60,
    '4h': 240,
    '1d': 1440,
    '1w': 10080,
    '15d': 21600
}

BASES = [
    'ETC', 'XMR', 'QTUM', 'ATOM',
    'XLM', 'DAI', 'XRP', 'LINK',
    'PAXG', 'GNO', 'REP', 'XDG',
    'MLN', 'ETH', 'ADA', 'BAT',
    'LSK', 'TRX', 'DASH', 'XTZ',
    'NANO', 'BTC', 'LTC', 'SC',
    'WAVES', 'ALGO', 'EOS', 'OMG',
    'BCH', 'ICX', 'ZEC'
]

SPECIAL_BASES = [
    'QTUM', 'ATOM', 'LINK', 'PAXG',
    'GNO', 'XDG', 'ADA', 'BAT',
    'LSK', 'TRX', 'DASH', 'XTZ',
    'NANO', 'WAVES', 'SC', 'ALGO',
    'EOS', 'OMG', 'BCH', 'ICX', 'DAI'
]

API_PUBLIC = {
    'Time',
    'Assets',
    'AssetPairs',
    'Ticker',
    'OHLC',
    'Depth',
    'Trades',
    'Spread'
}

API_PRIVATE = {
    'Balance',
    'TradeBalance',
    'OpenOrders',
    'ClosedOrders',
    'QueryOrders',
    'TradesHistory',
    'QueryTrades',
    'OpenPositions',
    'Ledgers',
    'QueryLedgers',
    'RemoveExport',
    'GetWebSocketsToken'
}

API_TRADING = {'AddOrder', 'CancelOrder'}

API_FUNDING = {
    'DepositMethods',
    'DepositAddresses',
    'DepositStatus',
    'WithdrawInfo',
    'Withdraw',
    'WithdrawStatus',
    'WithdrawCancel',
    'WalletTransfer'
}