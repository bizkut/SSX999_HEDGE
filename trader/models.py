# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021
 

import time as tm
import numpy as np
import pandas as pd
from ta.trend import ema_indicator

try:
    from trader import config
    from trader import utils
    from trader import Binance_API
except:
    import config
    import utils
    import Binance_API

class Currency(object):

    def __init__(self, max_nb_positions, capital):
        self.base = config.BASE
        self.quote = config.QUOTE
        self.pair = config.PAIR
        self.base_amount_precision = config.BASE_AMOUNT_PRECISION
        self.base_price_precision = config.BASE_PRICE_PRECISION
        self.timeframe = config.TIMEFRAME
        self.timedelta = pd.Timedelta(config.TIMEDELTA)
        self.capital = capital
        self.leverage = config.LEVERAGE
        self.stop_loss = config.STOP_LOSS
        self.take_profit = config.TAKE_PROFIT
        self.real_mode = config.REAL_MODE
        self.fee_rate = Binance_API.get_commission_rate(self.pair)['takerCommissionRate']
        
        self.id = 0
        self.n_open_positions = 0
        self.max_open_positions = max_nb_positions
        self.open_positions = dict()
        self.contracts = dict()
        for i in range(0, max_nb_positions):
            self.open_positions[i] = None
            self.contracts[i] = {
                'long': {'order': None, 'stop loss': None, 'take profit': None},
                'short': {'order': None, 'stop loss': None, 'take profit': None},                
            }
        self.LONG = []
        self.SHORT = []

        t = pd.Timestamp(int(tm.time()), unit='s')
        divider = int(pd.Timedelta(config.TIMEDELTA).to_timedelta64()/10**9/60)
        self.next_timestamp = pd.Timestamp(
            year=t.year,
            month=t.month,
            day=t.day,
            hour=(t.hour),
            minute=divider*(t.minute//divider) # if 'h' in config.TIMEFRAME else t.minute
        ) + self.timedelta

        while not Binance_API.is_hedge_mode():
            Binance_API.change_position_mode(True)
        Binance_API.change_margin_type(self.pair, 'CROSSED')

        return

    def find_available_position(self):
        """
        Returns index of the first available position or None if no position can be opened.
        """
        for i in range(0, self.max_open_positions):
            if self.open_positions[i] == None:
                return i
        return None

    def update_price(self):
        price = Binance_API.get_price(self.pair)
        return price

    def set_positions(self, position_idx):
        t = int(tm.time())

        if self.real_mode:
            long_price = np.float(self.contracts[position_idx]['long']['order']['avgPrice']) # or 'price'
            short_price = np.float(self.contracts[position_idx]['short']['order']['avgPrice']) # or 'price'
            # At this stage, if self.real_mode == True, amount is supposed to be the same on long and short sides
            qty = np.float(self.contracts[position_idx]['long']['order']['executedQty'])
            amount = qty * long_price

            long_stop_loss = np.float(self.contracts[position_idx]['long']['stop loss']['stopPrice'])
            short_stop_loss = np.float(self.contracts[position_idx]['short']['stop loss']['stopPrice'])

            long_take_profit = np.float(self.contracts[position_idx]['long']['take profit']['stopPrice'])
            short_take_profit = np.float(self.contracts[position_idx]['short']['take profit']['stopPrice'])
        else:
            close_price = self.update_price()
            long_price = close_price
            short_price = close_price
            amount = self.capital / (self.max_open_positions + 1 - self.n_open_positions)
            qty = round(np.floor(self.leverage * 0.45*amount/close_price * 10**config.BASE_AMOUNT_PRECISION) / (10**config.BASE_AMOUNT_PRECISION), 3)
            long_stop_loss = long_price * (1 - self.stop_loss)
            long_take_profit = long_price * (1 + self.take_profit)

            short_stop_loss = short_price * (1 + self.stop_loss)
            short_take_profit = short_price * (1 - self.take_profit)

        _long = {
            'entry time': t,
            'exit time': 0,
            'id': self.id,
            'entry': long_price,
            'exit': 0,
            'qty': qty,
            'leverage': self.leverage,
            'stop loss': long_stop_loss,
            'take profit': long_take_profit,
            'actualised': False,
        }
        _short = {
            'entry time': t,
            'exit time': 0,
            'id': self.id,
            'entry': short_price,
            'exit': 0,
            'qty': qty,
            'leverage': self.leverage,
            'stop loss': short_stop_loss,
            'take profit': short_take_profit,
            'actualised': False,
        }
        self.id += 1
        self.n_open_positions += 1
        self.capital -= (_long['entry']*_long['qty']/self.leverage + _short['entry']*_short['qty']/self.leverage)
        self.capital -= (self.fee_rate * (_long['entry']*_long['qty'] + _short['entry']*_short['qty']))
        self.open_positions[position_idx] = {'long': _long, 'short': _short}
        return

    def prepare_initial_orders(self):
        """
        Prepare all the settings to create simultaneous LONG & SHORT orders, plus initial stop loss and take profit orders.
        At this stage, no order is actually posted on the Binance account.
        
        To optimize the probability to open two opposite positions at the same entry price,
        the best order type is 'MARKET'.

        Arguments:
            amount (float): quote amount to allocate for the trade

        """
        # Security: garantee to not post orders in simulation mode
        if not self.real_mode:
            return

        # Prepare orders
        price = self.update_price()
        # We need to take into account the precision of a contract
        amount = self.capital / (self.max_open_positions + 1 - self.n_open_positions)
        qty = round(np.floor(0.45*self.leverage*amount/price * 10**config.BASE_AMOUNT_PRECISION) / (10**config.BASE_AMOUNT_PRECISION), 3)

        long_order = {
            'symbol': self.pair,
            'side': 'BUY',
            'positionSide': 'LONG',
            'type': 'MARKET',
            'quantity': str(qty)
        }
        short_order = {
            'symbol': self.pair,
            'side': 'SELL',
            'positionSide': 'SHORT',
            'type': 'MARKET',
            'quantity': str(qty)
        }
        return [long_order, short_order]
        
    def prepare_initial_activation_orders(self, position_idx):
        """
        After long & short initial orders have been placed, this function prepares the initial stop loss and take profit orders.
        """
        # Security: garantee to not post orders in simulation mode
        if not self.real_mode:
            return

        long_entry = np.float(self.contracts[position_idx]['long']['order']['avgPrice'])
        short_entry = np.float(self.contracts[position_idx]['short']['order']['avgPrice'])

        long_order_stop_loss = {
            'symbol': self.pair,
            'side': 'SELL',
            'positionSide': 'LONG',
            'type': 'STOP_MARKET',
            'workingType': 'MARK_PRICE',
            'priceProtect': 'TRUE',
            'quantity': str(self.contracts[position_idx]['long']['order']['executedQty']),
            'stopPrice': str(round(long_entry * (1-self.stop_loss), 2))
        }
        short_order_stop_loss = {
            'symbol': self.pair,
            'side': 'BUY',
            'positionSide': 'SHORT',
            'type': 'STOP_MARKET',
            'workingType': 'MARK_PRICE',
            'priceProtect': 'TRUE',
            'quantity': str(self.contracts[position_idx]['short']['order']['executedQty']),
            'stopPrice': str(round(short_entry * (1+self.stop_loss), 2))
        }
        long_order_take_profit = {
            'symbol': self.pair,
            'side': 'SELL',
            'positionSide': 'LONG',
            'type': 'TAKE_PROFIT_MARKET',
            'workingType': 'MARK_PRICE',
            'priceProtect': 'TRUE',
            'quantity': str(self.contracts[position_idx]['long']['order']['executedQty']),
            'stopPrice': str(round(long_entry * (1+self.take_profit), 2))
        }
        short_order_take_profit = {
            'symbol': self.pair,
            'side': 'BUY',
            'positionSide': 'SHORT',
            'type': 'TAKE_PROFIT_MARKET',
            'workingType': 'MARK_PRICE',
            'priceProtect': 'TRUE',
            'quantity': str(self.contracts[position_idx]['short']['order']['executedQty']),
            'stopPrice': str(round(short_entry * (1-self.take_profit), 2))
        }
        orders_list = [long_order_stop_loss, short_order_stop_loss, long_order_take_profit, short_order_take_profit]
        return orders_list

    def place_orders_simultaneously(self, order_list):
        recvWindow = 2000 if len(order_list) == 2 else 4000
        posted_orders = Binance_API.place_multiple_orders(order_list, recvWindow)       
        return posted_orders
    
    def cancel_order(self, orderId):
        order = Binance_API.cancel_order(self.pair, orderId)
        if 'status' in order.keys():
            if order['status'] != 'CANCELED':
                return self.cancel_order(orderId)
            else:
                return order
        else:
            return None

    def place_single_order(self, order_settings):
        order = Binance_API.create_order(order_settings)
        print(order)
        if not 'status' in order.keys():
            return self.place_single_order(order_settings)
        return order

    def is_stop_loss_activated(self, position_idx, position_side):
        """
        Returns True if stop loss has been filled during the last time interval, else False.

        Arguments:
            position_idx (int): studied position
            position_side (str): either 'long' or 'short'
        
        Response:
            True if stop loss activated recently, else False
        """
        # Case: real mode activated
        if self.real_mode:
            stop_loss_contract = self.contracts[position_idx][position_side]['stop loss']
            contract_status = Binance_API.query_order(self.pair, stop_loss_contract['orderId'])['status']
            case1 = (self.open_positions[position_idx][position_side]['actualised'] == False and contract_status == 'FILLED')
            case2 = (self.open_positions[position_idx][position_side]['actualised'] == True and contract_status == 'FILLED' and self.open_positions[position_idx][position_side]['exit'] == 0)
            return case1 or case2
        # Case: simulation mode
        else:
            if position_side == 'long':
                case1 = self.open_positions[position_idx]['long']['actualised'] == False and self.update_price() < self.open_positions[position_idx]['long']['stop loss']
                case2 = self.open_positions[position_idx]['long']['actualised'] == True and self.update_price() < self.open_positions[position_idx]['long']['stop loss']
                case2 = case2 and self.open_positions[position_idx]['long']['exit'] == 0
            else:
                case1 = self.open_positions[position_idx]['short']['actualised'] == False and self.update_price() > self.open_positions[position_idx]['short']['stop loss']
                case2 = self.open_positions[position_idx]['short']['actualised'] == True and self.update_price() > self.open_positions[position_idx]['short']['stop loss']
                case2 = case2 and self.open_positions[position_idx]['short']['exit'] == 0
            return case1 or case2

    def is_take_profit_activated(self, position_idx, position_side):
        """
        Returns True if take profit has been filled during the last time interval, else False.

        Arguments:
            position_idx (int): studied position
            position_side (str): either 'long' or 'short'
        
        Response:
            True if take profit activated recently, else False
        """
        if self.real_mode:
            take_profit_contract = self.contracts[position_idx][position_side]['take profit']
            contract_status = Binance_API.query_order(self.pair, take_profit_contract['orderId'])['status']
            case = (self.open_positions[position_idx][position_side]['actualised'] == True and contract_status == 'FILLED')
        else:
            if position_side == 'long':
                case = (self.open_positions[position_idx][position_side]['actualised'] == True and self.open_positions[position_idx][position_side]['take profit'] < self.update_price())
            else:
                case = (self.open_positions[position_idx][position_side]['actualised'] == True and self.open_positions[position_idx][position_side]['take profit'] > self.update_price())
        return case


    def update_ledgers(self, position_idx):
        # Update OrderLedger
        if self.real_mode:
            order_ledger = utils.read_csv(config.order_ledger_path)
            order_ledger = order_ledger.append(self.contracts[position_idx]['long']['order'], ignore_index=True)
            order_ledger = order_ledger.append(self.contracts[position_idx]['long']['stop loss'], ignore_index=True)
            order_ledger = order_ledger.append(self.contracts[position_idx]['long']['take profit'], ignore_index=True)
            order_ledger = order_ledger.append(self.contracts[position_idx]['short']['order'], ignore_index=True)
            order_ledger = order_ledger.append(self.contracts[position_idx]['short']['stop loss'], ignore_index=True)
            order_ledger = order_ledger.append(self.contracts[position_idx]['short']['take profit'], ignore_index=True)
            utils.dump_as_csv(order_ledger, config.order_ledger_path)
        return


    def close_position(self, position_idx):
        # Compute final trade stats
        self.open_positions[position_idx]['long']['type'] = 'LONG'
        self.open_positions[position_idx]['short']['type'] = 'SHORT'
        self.open_positions[position_idx]['long']['abs capital gain'] = (self.open_positions[position_idx]['long']['exit']/self.open_positions[position_idx]['long']['entry'] - 1) * self.leverage / 100
        self.open_positions[position_idx]['short']['abs capital gain'] = (self.open_positions[position_idx]['short']['entry']/self.open_positions[position_idx]['short']['exit'] - 1) * self.leverage / 100
        self.open_positions[position_idx]['long']['capital gain'] = self.open_positions[position_idx]['long']['abs capital gain'] * self.open_positions[position_idx]['long']['qty'] * self.open_positions[position_idx]['long']['entry']
        self.open_positions[position_idx]['short']['capital gain'] = self.open_positions[position_idx]['short']['abs capital gain'] * self.open_positions[position_idx]['short']['qty'] * self.open_positions[position_idx]['short']['exit']
        # Update TradeLedger
        trade_ledger = utils.read_csv(config.trade_ledger_path)
        trade_ledger = trade_ledger.append(self.open_positions[position_idx]['long'], ignore_index=True)
        trade_ledger = trade_ledger.append(self.open_positions[position_idx]['short'], ignore_index=True)
        utils.dump_as_csv(trade_ledger, config.trade_ledger_path)
        # Update capital & n_open_positions
        long = self.open_positions[position_idx]['long']
        short = self.open_positions[position_idx]['short']
        self.LONG.append(long)
        self.SHORT.append(short)
        self.update_capital()
        self.open_positions[position_idx] = None
        self.contracts[position_idx] = {
            'long': {'order': None, 'stop loss': None, 'take profit': None},
            'short': {'order': None, 'stop loss': None, 'take profit': None},                
        }
        self.n_open_positions -= 1
        return

    def load_latest_ohlc(self):
        """
        Returns latest ohlc candlestick (proportional to config.SLOW_PERIOD), with computed fast and slow EMAs.
        """
        limit = 3*config.SLOW_PERIOD
        ohlc = Binance_API.get_contract_klines(self.pair, self.timeframe, contractType='PERPETUAL', limit=limit)
        ohlc = pd.DataFrame(ohlc, columns=config.OHLC_COLUMNS)
        ohlc = ohlc[ohlc['open_time'] < 1000*(self.next_timestamp - self.timedelta).timestamp()]
        ohlc['ema_fast'] = ema_indicator(ohlc['close_price'], config.FAST_PERIOD)
        ohlc['ema_slow'] = ema_indicator(ohlc['close_price'], config.SLOW_PERIOD)
        return ohlc

    def update_contracts(self):
        for i in range(self.n_open_positions):
            for position_side in ['long', 'short']:
                sl_prev_status = self.contracts[i][position_side]['stop loss']['status']
                tp_prev_status = self.contracts[i][position_side]['take profit']['status']
                self.contracts[i][position_side]['stop loss'] = Binance_API.query_order(self.pair, self.contracts[i][position_side]['stop loss']['orderId'])
                self.contracts[i][position_side]['take profit'] = Binance_API.query_order(self.pair, self.contracts[i][position_side]['take profit']['orderId'])                 
                
                if self.open_positions[i][position_side]['actualised'] == True:
                    case_0 = (sl_prev_status != self.contracts[i][position_side]['stop loss']['status'])
                    case_1 = (tp_prev_status != self.contracts[i][position_side]['take profit']['status'])
                    if case_0 or case_1:
                        self.update_ledgers(i)
                        self.close_position(i)
                
        return

    def update_capital(self):
        if self.real_mode:
            available_account_balance = Binance_API.get_futures_account_balance()
            available_account_balance = available_account_balance['availableBalance']
            self.capital = available_account_balance
        return
