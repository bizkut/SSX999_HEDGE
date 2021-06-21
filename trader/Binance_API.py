# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import numpy as np
import time as tm
import hmac
import json
import hashlib
import requests
from urllib.parse import urlencode

from trader import utils
from trader import env
from trader import config


def read_keys():
    api_key = utils.read_file(path=config.public_key_path)
    api_secret = utils.read_file(path=config.private_key_path)
    return api_key, api_secret


KEY, SECRET = read_keys()
BASE_URL = 'https://fapi.binance.com'


# SETTING UP SIGNATURE
# --------------------

def hashing(query_string: str):
    """ Build hashed signature for identification """
    hmac_signature = hmac.new(SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
    return hmac_signature.hexdigest()


def dispatch_request(http_method: str):
    """ Prepare a request with given http method """
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json;charset=utf-8',
        'X-MBX-APIKEY': KEY
    })
    return {
        'GET': session.get,
        'DELETE': session.delete,
        'PUT': session.put,
        'POST': session.post,
    }.get(http_method, 'GET')


def send_signed_request(http_method: str, url_path: str, payload={}):
    """ 
    Prepare and send a signed request.
    Use this function to obtain private user info, manage trades and track accounts.
    """
    query_string = urlencode(payload)
    # Replace single quotes to double quotes
    query_string = query_string.replace('%27', '%22')
    if query_string:
        query_string = "{}&timestamp={}".format(query_string, get_server_time())
    else:
        query_string = 'timestamp={}'.format(get_server_time())
    url = BASE_URL + url_path + '?' + query_string + '&signature=' + hashing(query_string)
    params = {'url': url, 'params': {}}
    response = dispatch_request(http_method)(**params)
    return response.json()


def send_public_request(url_path: str, payload={}):
    """
    Prepare and send an unsigned request.
    Use this function to obtain public market data
    """
    query_string = urlencode(payload, True)
    url = BASE_URL + url_path
    if query_string:
        url = url + '?' + query_string
    response = dispatch_request('GET')(url=url)
    return response.json()


# GENERAL ENDPOINTS
# -----------------

def test_connectivity():
    """ Check if server is on or not """
    url_path = '/fapi/v1/ping'
    ping = send_public_request(url_path)
    return ping == {}


def get_server_time():
    """ Returns current time in milliseconds on the Binance server (it can be different from local time)"""
    url_path = '/fapi/v1/time'
    serverTime = send_public_request(url_path)['serverTime']
    return serverTime


def get_exchange_info():
    """ Returns current exchange trading rules and symbols information """
    url_path = '/fapi/v1/exchangeInfo'
    exchange_info = send_public_request(url_path)
    return exchange_info


# GENERAL ENDPOINTS
# -----------------

def get_order_book(pair: str, limit=20):
    """
    Returns bids and asks for the specified pair.

    Arguments:
        pair (str): single pair
        limit (int): Valid limits are [5, 10, 20, 50, 100, 500, 1000]

    Response:
        {
            'lastUpdateId' (int),
            'E' (unix timestamp), 
            'T' (unix timestamp),
            'bids' (list of [price (str), quantity (str)]),
            'asks' (list of [price (str), quantity (str)])
        }
    """
    url_path = '/fapi/v1/depth'
    params = {'symbol': pair.upper(), 'limit': limit}
    order_book = send_public_request(url_path, params)
    for i in range(limit):
        order_book['bids'][i] = [np.float64(order_book['bids'][i][0]), np.float64(order_book['bids'][i][1])]
        order_book['asks'][i] = [np.float64(order_book['asks'][i][0]), np.float64(order_book['asks'][i][1])]
    return order_book


def get_recent_trades(pair: str, limit=20):
    """
    Returns the latest trades performed on the Binance Futures market.
    
    Arguments:
        pair (str): single pair
        limit (int): less or equal to 1000
    
    Response:
        list of trades: [
            {
                'id' (int),
                'price' (float),
                'qty' (float),
                'quoteQty' (float),
                'time' (unix timestamp),
                'isBuyerMaker' (bool)
            }
        ]
    """
    url_path = '/fapi/v1/trades'
    params = {'symbol': pair.upper(), 'limit': limit}
    trades = send_public_request(url_path, params)
    for trade in trades:
        trade['price'] = np.float64(trade['price'])
        trade['qty'] = np.float64(trade['qty'])
        trade['quoteQty'] = np.float64(trade['quoteQty'])
    return trades


def get_old_trades(pair: str, limit=100, fromId=None):
    """
    Get older market historical trades.

    Arguments:
        pair (str): single pair
        limit (int): less or equal to 1000
        fromId (int): Trade Id to fetch from (optional). Default gets most recent trades.

    Response:
        list of trades: [
            {
                'id' (int),
                'price' (float),
                'qty' (float),
                'quoteQty' (float),
                'time' (unix timestamp),
                'isBuyerMaker' (bool)
            }
        ]
    """
    url_path = '/fapi/v1/historicalTrades'
    params = {'symbol': pair.upper(), 'limit': limit}
    if fromId != None:
        params['fromId'] = fromId
    trades = send_public_request(url_path, params)
    # Convert str to float
    for trade in trades:
        trade['price'] = np.float64(trade['price'])
        trade['qty'] = np.float64(trade['qty'])
        trade['quoteQty'] = np.float64(trade['quoteQty'])
    return trades


def get_klines(pair: str, intervals: str, startTime=None, endTime=None, limit=1500):
    """
    Get candlestick bars (called klines) for a symbol. Klines are uniquely identified by their open time.
    If startTime and endTime are not sent, the most recent klines are returned.

    Arguments:
        pair (str): single pair
        intervals (list): timeframes to get candlesticks data
            ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        startTime (unix timestamp): start time in ms unix timestamp (inclusive)
        endTime (unix timestamp): end time in ms unix timestamp (inclusive)
        limit (int): less or equal to 1500

    Response:
        list of lists [
            [
                Open Time (ms unix timestamp)
                Open Price (float)
                High Price (float)
                Low Price (float)
                Close Price (float)
                Volume (float)
                Close Time (ms unix timestamp)
                Quote asset volume (float)
                Number of trades (int)
                Taker buy base asset volume (float)
                Taker buy quote asset volume (float)
            ]
        ]
    """
    url_path = '/fapi/v1/klines'
    params = {'symbol': pair.upper(), 'interval': intervals, 'limit': limit}
    if startTime != None:
        params['startTime'] = startTime
    if endTime != None:
        params['endTime'] = endTime
    klines = send_public_request(url_path, params)
    # Convert str to float
    for i in range(len(klines)):
        klines[i] = [
            klines[i][0],
            np.float64(klines[i][1]),
            np.float64(klines[i][2]),
            np.float64(klines[i][3]),
            np.float64(klines[i][4]),
            np.float64(klines[i][5]),
            klines[i][6],
            np.float64(klines[i][7]),
            klines[i][8],
            np.float64(klines[i][9]),
            np.float64(klines[i][10]),
        ]
    return klines


def get_contract_klines(pair: str, intervals: str, contractType='PERPETUAL', startTime=None, endTime=None, limit=1500):
    """
    Get candlestick bars (called klines) for a specific contract type and symbol. Klines are uniquely identified by their open time.
    If startTime and endTime are not sent, the most recent klines are returned.

    Arguments:
        pair (str): single pair
        intervals (list): timeframes to get candlesticks data
            ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        contractType (list): valid contract types are [PERPETUAL, CURRENT_MONTH, NEXT_MONTH, CURRENT_QUARTER, NEXT_QUARTER]
        startTime (unix timestamp): start time in ms unix timestamp (inclusive)
        endTime (unix timestamp): end time in ms unix timestamp (inclusive)
        limit (int): less or equal to 1500

    Response:
        list of lists [
            [
                Open Time (ms unix timestamp)
                Open Price (float)
                High Price (float)
                Low Price (float)
                Close Price (float)
                Volume (float)
                Close Time (ms unix timestamp)
                Quote asset volume (float)
                Number of trades (int)
                Taker buy base asset volume (float)
                Taker buy quote asset volume (float)
            ]
        ]
    """
    url_path = '/fapi/v1/continuousKlines'
    params = {'pair': pair.upper(), 'interval': intervals, 'limit': limit, 'contractType': contractType}
    if startTime != None:
        params['startTime'] = startTime
    if endTime != None:
        params['endTime'] = endTime
    klines = send_public_request(url_path, params)
    # Convert str to float
    for i in range(len(klines)):
        klines[i] = [
            klines[i][0],
            np.float64(klines[i][1]),
            np.float64(klines[i][2]),
            np.float64(klines[i][3]),
            np.float64(klines[i][4]),
            np.float64(klines[i][5]),
            klines[i][6],
            np.float64(klines[i][7]),
            klines[i][8],
            np.float64(klines[i][9]),
            np.float64(klines[i][10]),
        ]
    return klines


def get_price(pair: str):
    """
    Get latest price for a symbol.

    Arguments:
        pair (str): single pair
    
    Response:

    """
    url_path = '/fapi/v1/ticker/price'
    params = {'symbol': pair}
    ticker = send_public_request(url_path, params)
    price = np.float64(ticker['price'])
    return price


# ACCOUNT ENDPOINTS
# -----------------

def get_futures_account_balance(recvWindow=1000):
    """
    Read Futures account balance (V2)

    Arguments:
        recvWindow (int): number of milliseconds after which the request must be cancelled

    Response:
        account_balance (list of dict): [
            {
                "accountAlias": "SgsR",    // unique account code
                "asset": "USDT",    // asset name
                "balance": "122607.35137903", // wallet balance
                "crossWalletBalance": "23.72469206", // crossed wallet balance
                "crossUnPnl": "0.00000000"  // unrealized profit of crossed positions
                "availableBalance": "23.72469206",       // available balance
                "maxWithdrawAmount": "23.72469206",     // maximum amount for transfer out
                "marginAvailable": true,    // whether the asset can be used as margin in Multi-Assets mode
                "updateTime": 1617939110373
            }
        ]
    """
    url_path = '/fapi/v2/balance'
    params = {'recvWindow': recvWindow}
    account_balance = send_signed_request('GET', url_path, params)
    # convert numeric fields to float
    for balance in account_balance:
        balance['balance'] = np.float64(balance['balance'])
        balance['crossWalletBalance'] = np.float64(balance['crossWalletBalance'])
        balance['crossUnPnl'] = np.float64(balance['crossUnPnl'])
        balance['availableBalance'] = np.float64(balance['availableBalance'])
        balance['maxWithdrawAmount'] = np.float64(balance['maxWithdrawAmount'])
        balance['updateTime'] = np.float64(balance['updateTime'])
    for balance in account_balance:
        if balance['asset'] == 'USDT':
            return balance
    return None


def is_hedge_mode(recvWindow=1000):
    """
    Get user's position mode (Hedge Mode or One-way Mode ) on EVERY symbols.

    Arguments:
        recvWindow (int): number of milliseconds after which the request must be cancelled

    Response:
        dualSidePosition (bool): True=>HedgeMode active | False=>OneWayMode active
    """
    url_path = '/fapi/v1/positionSide/dual'
    params = {'recvWindow': recvWindow}
    dualSidePosition = send_signed_request('GET', url_path, params)['dualSidePosition']
    return dualSidePosition


def change_position_mode(hedgeMode: bool, recvWindow=1000):
    """
    Change user's position mode (Hedge Mode or One-way Mode ) on EVERY symbols.

    Arguments:
        hedgeMode (bool): True=>HedgeMode | False=>OneWayMode
        recvWindow (int): number of milliseconds after which the request must be cancelled

    """
    if is_hedge_mode() == hedgeMode:
        return True
    url_path = '/fapi/v1/positionSide/dual'
    params = {'dualSidePosition': hedgeMode, 'recvWindow': recvWindow}
    resp = send_signed_request('POST', url_path, params)
    return resp


def create_order(order_settings: dict):
    """
    Send in a new order.

    Arguments:
        order_settings (dict): {
            'symbol' (str): single pair (mandatory)
            'side' (enum): ['BUY', 'SELL'] (mandatory) 
            'positionSide' (enum): ['BOTH' for OneWayMode, 'LONG' or 'SHORT' for HedgeMode]
            'type' (enum): ['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET'] (mandatory)
            'timeInForce' (enum): ['GTC', 'IOC', 'FOK', 'GTX' (post only)]
            'quantity' (float): quantity of asset to purchase
            'reduceOnly' (str): ['true' or 'false']. Cannot be sent in HedgeMode, nor with closePosition='true'
            'price' (float): necessary when order type is LIMIT
            'stopPrice' (float): used with STOP/STOP_MARKET or TAKE_PROFIT/TAKE_PROFIT_MARKET orders
            'closePosition' (str): 
            'priceProtect' (str):
            'newOrderRespType' (enum):
            'recvWindow' (int):
        }
    
    Response:
        {
            "clientOrderId": "testOrder",
            "cumQty": "0",
            "cumQuote": "0",
            "executedQty": "0",
            "orderId": 22542179,
            "avgPrice": "0.00000",
            "origQty": "10",
            "price": "0",
            "reduceOnly": false,
            "side": "BUY",
            "positionSide": "SHORT",
            "status": "NEW",
            "stopPrice": "9300",        // please ignore when order type is TRAILING_STOP_MARKET
            "closePosition": false,   // if Close-All
            "symbol": "BTCUSDT",
            "timeInForce": "GTC",
            "type": "TRAILING_STOP_MARKET",
            "origType": "TRAILING_STOP_MARKET",
            "activatePrice": "9020",    // activation price, only return with TRAILING_STOP_MARKET order
            "priceRate": "0.3",         // callback rate, only return with TRAILING_STOP_MARKET order
            "updateTime": 1566818724722,
            "workingType": "CONTRACT_PRICE",
            "priceProtect": false            // if conditional order trigger is protected   
        }
    """
    url_path = '/fapi/v1/order'
    order = send_signed_request('POST', url_path, order_settings)
    labels_to_convert = ['cumQty', 'cumQuote', 'executedQty', 'avgPrice', 'origQty', 'price', 'stopPrice', 'activatePrice', 'priceRate']
    for label in order.keys():
        if label in labels_to_convert:
            order[label] = np.float64(order[label])
    return order


def place_mutliple_orders(all_order_settings: list, recvWindow=1000):
    """
    Send in a new order.

    Arguments:
        all_order_settings (list of dict): max length of 5
        {
            'symbol' (str): single pair (mandatory)
            'side' (enum): ['BUY', 'SELL'] (mandatory) 
            'positionSide' (enum): ['BOTH' for OneWayMode, 'LONG' or 'SHORT' for HedgeMode]
            'type' (enum): ['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET', 'TAKE_PROFIT', 'TAKE_PROFIT_MARKET', 'TRAILING_STOP_MARKET'] (mandatory)
            'timeInForce' (enum): ['GTC', 'IOC', 'FOK', 'GTX' (post only)]
            'quantity' (float): quantity of asset to purchase
            'reduceOnly' (str): ['true' or 'false']. Cannot be sent in HedgeMode, nor with closePosition='true'
            'price' (float): necessary when order type is LIMIT
            'stopPrice' (float): used with STOP/STOP_MARKET or TAKE_PROFIT/TAKE_PROFIT_MARKET orders
            'closePosition' (str): 
            'priceProtect' (str):
            'newOrderRespType' (enum):
        }
    
    Response:
        {
            "clientOrderId": "testOrder",
            "cumQty": "0",
            "cumQuote": "0",
            "executedQty": "0",
            "orderId": 22542179,
            "avgPrice": "0.00000",
            "origQty": "10",
            "price": "0",
            "reduceOnly": false,
            "side": "BUY",
            "positionSide": "SHORT",
            "status": "NEW",
            "stopPrice": "9300",        // please ignore when order type is TRAILING_STOP_MARKET
            "closePosition": false,   // if Close-All
            "symbol": "BTCUSDT",
            "timeInForce": "GTC",
            "type": "TRAILING_STOP_MARKET",
            "origType": "TRAILING_STOP_MARKET",
            "activatePrice": "9020",    // activation price, only return with TRAILING_STOP_MARKET order
            "priceRate": "0.3",         // callback rate, only return with TRAILING_STOP_MARKET order
            "updateTime": 1566818724722,
            "workingType": "CONTRACT_PRICE",
            "priceProtect": false            // if conditional order trigger is protected   
        }
    """
    url_path = '/fapi/v1/batchOrders'
    if len(all_order_settings) > 5 or len(all_order_settings) < 1:
        return None
    all_orders = [json.dumps(order) for order in all_order_settings]
    all_orders = '[' + ','.join(all_orders) + ']'
    params = {'batchOrders': all_orders, 'recvWindow': recvWindow}
    orders = send_signed_request('POST', url_path, params)
    labels_to_convert = ['cumQty', 'cumQuote', 'executedQty', 'avgPrice', 'origQty', 'price', 'stopPrice', 'activatePrice', 'priceRate']
    for i in range(len(orders)):
        for label in orders[i].keys():
            if label in labels_to_convert:
                orders[i][label] = np.float64(orders[i][label])
    return orders


def query_order(pair: str, orderId: int, recvWindow=1000):
    """
    Check an order's status.

    Arguments:
        pair (str): single pair
        orderId (int): Id of the order to look for status
        recvWindow (int): time in milliseconds after which the request must be aborted

    Response:
        order
    """
    url_path = '/fapi/v1/order'
    params = {'symbol': pair, 'orderId': orderId, 'recvWindow': recvWindow}
    order = send_signed_request('GET', url_path, params)
    return order


def query_current_all_open_orders(pair: str, recvWindow=1000):
    """
    Get all open orders on a symbol. Careful when accessing this with no symbol.

    Arguments:
        pair (str): single pair
        recvWindow (int): time in milliseconds after which the request must be aborted

    Response:
        status (str)
    """
    url_path = '/fapi/v1/openOrders'
    params = {'symbol': pair, 'recvWindow':recvWindow}
    orders = send_signed_request('GET', url_path, params)
    orders = [{'orderId': orders[i]['orderId'], 'status': orders[i]['status']} for i in range(len(orders))]
    return orders


def cancel_order(pair: str, orderId: int, recvWindow=1000):
    """
    Cancel an active order.

    Arguments:
        pair (str): single pair
        orderId (int): Id of the order to look for status
        recvWindow (int): time in milliseconds after which the request must be aborted

    Response:
        True if order has been successfully canceled, else False 
    """
    url_path = '/fapi/v1/order'
    params = {'symbol': pair, 'orderId': orderId, 'recvWindow': recvWindow}
    response = send_signed_request('DELETE', url_path, params)
    return response['status'] == 'CANCELED'


def cancel_all_open_orders(pair: str, recvWindow=1000):
    """
    Cancel all active orders.

    Arguments:
        pair (str): single pair
        recvWindow (int): time in milliseconds after which the request must be aborted

    Response:
        True if orders have been successfully canceled, else False 
    """
    url_path = '/fapi/v1/allOpenOrders'
    params = {'symbol': pair, 'recvWindow': recvWindow}
    response = send_signed_request('DELETE', url_path, params)
    return response['code'] == 200


def change_initial_leverage(pair: str, leverage: int, recvWindow=1000):
    """
    Change user's initial leverage of specific symbol market.

    Arguments:
        pair (str): single pair
        leverage (int): between 1 and 125
        recvWindow (int): time in milliseconds after which the request must be aborted

    Response:
        leverage_set (dict): {
            "leverage": 21,
            "maxNotionalValue": 1000000,
            "symbol": "BTCUSDT"
        }
    """
    url_path = '/fapi/v1/leverage'
    params = {'symbol': pair, 'leverage': leverage, 'recvWindow': recvWindow}
    leverage_set = send_signed_request('POST', url_path, params)
    leverage_set['maxNotionalValue'] = np.float64(leverage_set['maxNotionalValue'])
    return leverage_set


def change_margin_type(pair: str, marginType: str, recvWindow=1000):
    """
    Set margin type as either 'ISOLATED' or 'CROSSED' for a specific pair.

    Arguments:
        pair (str): single pair
        marginType (str): either 'ISOLATED' or 'CROSSED'
        recvWindow (int): time in milliseconds after which the request must be aborted.

    Response:
        True if margin type changed successfully, else False
    """
    # Check if marginType needs to be changed
    current_marginType = get_current_position_information(pair)[0]['marginType']
    current_marginType = 'CROSSED' if current_marginType == 'cross' else 'ISOLATED'
    if current_marginType == marginType:
        return True
    url_path = '/fapi/v1/marginType'
    params = {'symbol': pair, 'marginType': marginType, 'recvWindow': recvWindow}
    response = send_signed_request('POST', url_path, params)
    if not response['code'] == '200':
        return change_margin_type(pair, marginType)
    else:
        return response['code'] == '200'


def get_current_position_information(pair: str, recvWindow=1000):
    """
    Get current position information.

    Arguments:
        pair (str): single pair
        recvWindow (int): time in milliseconds after which the request must be aborted.

    Response:
        positions (list of dict): [{
            'entryPrice': 6563.66500, 
            'marginType': 'isolated', 
            'isAutoAddMargin': False,
            'isolatedMargin': 15517.54150468,
            'leverage': 10,
            'liquidationPrice': 5930.78,
            'markPrice': 6679.50671178,   
            'maxNotionalValue': 20000000, 
            'positionAmt': 20.000, 
            'symbol': 'BTCUSDT', 
            'unRealizedProfit': 2316.83423560
            'positionSide': 'LONG', 
        }]
    """
    url_path = '/fapi/v2/positionRisk'
    params = {'symbol': pair, 'recvWindow': recvWindow}
    positions = send_signed_request('GET', url_path, params)
    # Convert to floats
    for position in positions:
        position['entryPrice'] = np.float64(position['entryPrice'])
        position['isolatedMargin'] = np.float64(position['isolatedMargin'])
        position['leverage'] = np.float64(position['leverage'])
        position['liquidationPrice'] = np.float64(position['liquidationPrice'])
        position['maxNotionalValue'] = np.float64(position['maxNotionalValue'])
        position['markPrice'] = np.float64(position['markPrice'])
        position['positionAmt'] = np.float64(position['positionAmt'])
        position['unRealizedProfit'] = np.float64(position['unRealizedProfit'])
        position['notional'] = np.float64(position['notional'])
        position['isolatedWallet'] = np.float64(position['isolatedWallet'])
        position['isAutoAddMargin'] = False if position['isAutoAddMargin'] == 'false' else True
    return positions


def is_margin_cross(pair: str, recvWindow=1000):
    margin_type = get_current_position_information(pair, recvWindow)[0]['marginType']
    return margin_type == 'cross'


def get_commission_rate(pair: str, recvWindow=1000):
    """
    Get user's current commission rates for a specific pair.

    Arguments:
        pair (str): single pair
        recvWindow (int): time in milliseconds after which the request must be aborted.
    """
    url_path = '/fapi/v1/commissionRate'
    params = {'symbol': pair, 'recvWindow': recvWindow}
    try:
        rates = send_signed_request('GET', url_path, params)
        rates['makerCommissionRate'] = np.float64(rates['makerCommissionRate'])
        rates['takerCommissionRate'] = np.float64(rates['takerCommissionRate'])
        return rates
    except:
        return get_commission_rate(pair, recvWindow)
    
    