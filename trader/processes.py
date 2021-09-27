# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021

import numpy as np
import pandas as pd
import time as tm
import logging

try:    
    from trader import Binance_API
    from trader import config
    from trader import models
    from trader import utils
except:
    import Binance_API
    import config
    import models
    import utils

logger = logging.getLogger('trader')
logger.setLevel(logging.DEBUG)

def check_api_keys_functional(TradedCurrency):
    try:
        is_cross = Binance_API.is_margin_cross(TradedCurrency.pair)
    except:
        logger.error('Error: Wrong API credentials. [continue_recurrent_algorithm: error1]')
        return
    return is_cross


def check_margin_type(TradedCurrency, is_cross):
    try:
        counter = 0
        while not is_cross and counter < 10:
            Binance_API.change_margin_type(TradedCurrency.pair, 'CROSSED')
            is_cross = Binance_API.is_margin_cross(TradedCurrency.pair)
            counter += 1
    except:
        error_msg = f'Error: Cannot set margin type to \'CROSSED\' for {TradedCurrency.pair}.'
        error_msg += f' Please, manually verify that Futures account for {TradedCurrency.pair} is correctly set up.'
        error_msg += ' [continue_recurrent_algorithm: error2]'
        logger.error(error_msg)
        return
    return


def check_position_mode():
    try:
        counter = 0
        while not Binance_API.is_hedge_mode() and counter < 10:
            Binance_API.change_position_mode(True)
            counter += 1
    except:
        error_msg = f'Error: Cannot set position mode to hedge mode.'
        error_msg += f' Please, manually verify that no order is active or pending on the whole Futures account.'
        error_msg += ' [continue_recurrent_algorithm: error3]'
        logger.error(error_msg)
        return
    return


def wait_for_next_timestamp(TradedCurrency):
    try:
        counter = 0
        server_time = Binance_API.get_server_time() / 1000
        while server_time < TradedCurrency.next_timestamp.timestamp() and counter < 10:
            sleep_time = int(TradedCurrency.next_timestamp.timestamp() - server_time + 2)
            print(f'Sleep for {sleep_time} seconds')
            tm.sleep(sleep_time)
            server_time = Binance_API.get_server_time() / 1000
            counter += 1
    except:
        error_msg = f'Error: Either cannot get server time (API overloaded) or next timestamp never reached'
        error_msg += f" Server time: {pd.Timestamp(server_time, unit='s')}"
        error_msg += f" Next timestamp: {TradedCurrency.next_timestamp}"
        error_msg += ' [continue_recurrent_algorithm: error4]'
        print(error_msg)
        return
    return


def first_long_stop_loss_activation(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Contract is filled => update : long position (exit, exit time, actualised) & short position (stop loss, actualised)
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['long']['stop loss'] = filled_contract
        TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['long']['exit'] = np.float(filled_contract['avgPrice'])
        TradedCurrency.open_positions[i]['long']['actualised'] = True
        TradedCurrency.contracts[i]['long']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        # Cancel previous short contract stop loss & open a new one (with stop at entry but unchanged profit)
        TradedCurrency.contracts[i]['short']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])

        price = Binance_API.get_price(TradedCurrency.pair)
        counter = 0
        while not (price < np.float(TradedCurrency.open_positions[i]['long']['exit']*(1-2*TradedCurrency.fee_rate))) and counter < 60:
            tm.sleep(30)
            counter += 1
            price = Binance_API.get_price(TradedCurrency.pair)
        if price < np.float(TradedCurrency.open_positions[i]['long']['exit']*(1-2*TradedCurrency.fee_rate)):
            order_settings = {
                'symbol': TradedCurrency.pair,
                'side': 'BUY',
                'positionSide': 'SHORT',
                'type': 'STOP_MARKET',
                'workingType': 'MARK_PRICE',
                'priceProtect': 'TRUE',
                'quantity': str(TradedCurrency.contracts[i]['short']['order']['executedQty']),
                'stopPrice': str(round(np.float(TradedCurrency.open_positions[i]['long']['exit']*(1-2*TradedCurrency.fee_rate)), config.BASE_PRICE_PRECISION)) # + 10
            }
            TradedCurrency.contracts[i]['short']['stop loss'] = TradedCurrency.place_single_order(order_settings)
        else:
            order_settings = {
                'symbol': TradedCurrency.pair,
                'side': 'BUY',
                'positionSide': 'SHORT',
                'type': 'MARKET',
                'quantity': str(TradedCurrency.contracts[i]['short']['order']['executedQty'])
            }
            TradedCurrency.contracts[i]['short']['stop loss'] = TradedCurrency.place_single_order(order_settings)
            TradedCurrency.contracts[i]['short']['stop loss'] = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
            TradedCurrency.open_positions[i]['short']['stop loss'] = np.float(TradedCurrency.contracts[i]['short']['stop loss']['avgPrice'])
            TradedCurrency.open_positions[i]['short']['actualised'] = True
            TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
            TradedCurrency.open_positions[i]['short']['exit'] = TradedCurrency.open_positions[i]['short']['stop loss']
            TradedCurrency.contracts[i]['short']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
            TradedCurrency.update_ledgers(i)
            TradedCurrency.close_position(i)

            # Update portfolio content according to Binance Futures account balance
            account_balance = Binance_API.get_futures_account_balance() 
            if not TradedCurrency.real_mode:
                account_balance['balance'] = TradedCurrency.capital
            df_balance = utils.read_csv(config.balance_path)
            df_balance = df_balance.append(account_balance, ignore_index=True)
            utils.dump_as_csv(df_balance, config.balance_path)
            return TradedCurrency


        # elif price >= np.float(TradedCurrency.open_positions[i]['long']['exit']) + config.EPSILON:
        #     order_settings = {
        #         'symbol': TradedCurrency.pair,
        #         'side': 'BUY',
        #         'positionSide': 'SHORT',
        #         'type': 'MARKET',
        #         'quantity': str(TradedCurrency.contracts[i]['short']['order']['executedQty'])
        #     }
        #     TradedCurrency.contracts[i]['short']['stop loss'] = TradedCurrency.place_single_order(order_settings)
            
        #     TradedCurrency.open_positions[i]['short']['stop loss'] = np.float(TradedCurrency.contracts[i]['short']['stop loss']['avgPrice'])
        #     TradedCurrency.open_positions[i]['short']['actualised'] = True
        #     TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        #     TradedCurrency.open_positions[i]['short']['exit'] = TradedCurrency.open_positions[i]['short']['stop loss']
        #     TradedCurrency.contracts[i]['short']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        #     TradedCurrency.update_ledgers(i)
        #     TradedCurrency.close_position(i)

        #     # Update portfolio content according to Binance Futures account balance
        #     account_balance = Binance_API.get_futures_account_balance() 
        #     if not TradedCurrency.real_mode:
        #         account_balance['balance'] = TradedCurrency.capital
        #     df_balance = utils.read_csv(config.balance_path)
        #     df_balance = df_balance.append(account_balance, ignore_index=True)
        #     utils.dump_as_csv(df_balance, config.balance_path)
        #     return TradedCurrency
        # else:
        #     order_settings = {
        #         'symbol': TradedCurrency.pair,
        #         'side': 'BUY',
        #         'positionSide': 'SHORT',
        #         'type': 'STOP_MARKET',
        #         'workingType': 'MARK_PRICE',
        #         'priceProtect': 'TRUE',
        #         'quantity': str(TradedCurrency.contracts[i]['short']['order']['executedQty']),
        #         'stopPrice': str(round(np.float(TradedCurrency.open_positions[i]['long']['exit']) + config.EPSILON, config.BASE_PRICE_PRECISION))
        #     }
        #     TradedCurrency.contracts[i]['short']['stop loss'] = TradedCurrency.place_single_order(order_settings)

        TradedCurrency.open_positions[i]['short']['stop loss'] = TradedCurrency.contracts[i]['short']['stop loss']['stopPrice']
        TradedCurrency.open_positions[i]['short']['actualised'] = True
    else:
        TradedCurrency.open_positions[i]['long']['exit'] = TradedCurrency.open_positions[i]['long']['stop loss']
        TradedCurrency.open_positions[i]['long']['actualised'] = True
        TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['short']['stop loss'] = TradedCurrency.open_positions[i]['long']['stop loss'] * (1-TradedCurrency.fee_rate)
        money_back = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['exit']
        money_back -= ((TradedCurrency.leverage - 1) / TradedCurrency.leverage * TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry'])
        TradedCurrency.capital += money_back
        TradedCurrency.capital -= TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['exit'] * TradedCurrency.fee_rate
    
    TradedCurrency.update_capital()
    return TradedCurrency


def first_short_stop_loss_activation(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Contract is filled => update : short position (exit, exit time, actualised) & long position (stop loss, actualised)
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['short']['stop loss'] = filled_contract
        TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['short']['exit'] = np.float(filled_contract['avgPrice'])
        TradedCurrency.open_positions[i]['short']['actualised'] = True
        TradedCurrency.contracts[i]['short']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        # Cancel previous short contract stop loss & open a new one (with stop at entry but unchanged profit)
        TradedCurrency.contracts[i]['long']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        
        price = Binance_API.get_price(TradedCurrency.pair)
        counter = 0
        while not (price > np.float(TradedCurrency.open_positions[i]['short']['exit']*(1+2*TradedCurrency.fee_rate))) and counter < 60:
            tm.sleep(30)
            counter += 1
            price = Binance_API.get_price(TradedCurrency.pair)
        if price > np.float(TradedCurrency.open_positions[i]['short']['exit']*(1+2*TradedCurrency.fee_rate)):
            order_settings = {
                'symbol': TradedCurrency.pair,
                'side': 'SELL',
                'positionSide': 'LONG',
                'type': 'STOP_MARKET',
                'workingType': 'MARK_PRICE',
                'priceProtect': 'TRUE',
                'quantity': str(TradedCurrency.contracts[i]['long']['order']['executedQty']),
                'stopPrice': str(round(np.float(TradedCurrency.open_positions[i]['short']['exit']*(1+2*TradedCurrency.fee_rate)), config.BASE_PRICE_PRECISION))
            }
            TradedCurrency.contracts[i]['long']['stop loss'] = TradedCurrency.place_single_order(order_settings)

        else:
            order_settings = {
                'symbol': TradedCurrency.pair,
                'side': 'SELL',
                'positionSide': 'LONG',
                'type': 'MARKET',
                'quantity': str(TradedCurrency.contracts[i]['long']['order']['executedQty'])
            }
            TradedCurrency.contracts[i]['long']['stop loss'] = TradedCurrency.place_single_order(order_settings)
            TradedCurrency.contracts[i]['long']['stop loss'] = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])

            TradedCurrency.open_positions[i]['long']['stop loss'] = np.float(TradedCurrency.contracts[i]['long']['stop loss']['avgPrice'])
            TradedCurrency.open_positions[i]['long']['actualised'] = True
            TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
            TradedCurrency.open_positions[i]['long']['exit'] = TradedCurrency.open_positions[i]['long']['stop loss']
            TradedCurrency.contracts[i]['long']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
            TradedCurrency.update_ledgers(i)
            TradedCurrency.close_position(i)

            # Update portfolio content according to Binance Futures account balance
            account_balance = Binance_API.get_futures_account_balance() 
            if not TradedCurrency.real_mode:
                account_balance['balance'] = TradedCurrency.capital
            df_balance = utils.read_csv(config.balance_path)
            df_balance = df_balance.append(account_balance, ignore_index=True)
            utils.dump_as_csv(df_balance, config.balance_path)
            return TradedCurrency

        # elif price <= np.float(TradedCurrency.open_positions[i]['short']['exit']) - config.EPSILON:
        #     order_settings = {
        #         'symbol': TradedCurrency.pair,
        #         'side': 'SELL',
        #         'positionSide': 'LONG',
        #         'type': 'MARKET',
        #         'quantity': str(TradedCurrency.contracts[i]['long']['order']['executedQty'])
        #     }
        #     TradedCurrency.contracts[i]['long']['stop loss'] = TradedCurrency.place_single_order(order_settings)
            
        #     TradedCurrency.open_positions[i]['long']['stop loss'] = np.float(TradedCurrency.contracts[i]['long']['stop loss']['avgPrice'])
        #     TradedCurrency.open_positions[i]['long']['actualised'] = True
        #     TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        #     TradedCurrency.open_positions[i]['long']['exit'] = TradedCurrency.open_positions[i]['long']['stop loss']
        #     TradedCurrency.contracts[i]['long']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        #     TradedCurrency.update_ledgers(i)
        #     TradedCurrency.close_position(i)

        #     # Update portfolio content according to Binance Futures account balance
        #     account_balance = Binance_API.get_futures_account_balance() 
        #     if not TradedCurrency.real_mode:
        #         account_balance['balance'] = TradedCurrency.capital
        #     df_balance = utils.read_csv(config.balance_path)
        #     df_balance = df_balance.append(account_balance, ignore_index=True)
        #     utils.dump_as_csv(df_balance, config.balance_path)
        #     return TradedCurrency
        # else:
        #     order_settings = {
        #         'symbol': TradedCurrency.pair,
        #         'side': 'SELL',
        #         'positionSide': 'LONG',
        #         'type': 'STOP_MARKET',
        #         'workingType': 'MARK_PRICE',
        #         'priceProtect': 'TRUE',
        #         'quantity': str(TradedCurrency.contracts[i]['long']['order']['executedQty']),
        #         'stopPrice': str(round(np.float(TradedCurrency.open_positions[i]['short']['exit']) - config.EPSILON, config.BASE_PRICE_PRECISION))
        #     }
        #     TradedCurrency.contracts[i]['long']['stop loss'] = TradedCurrency.place_single_order(order_settings)

        TradedCurrency.open_positions[i]['long']['stop loss'] = TradedCurrency.contracts[i]['long']['stop loss']['stopPrice']
        TradedCurrency.open_positions[i]['long']['actualised'] = True
    else:
        TradedCurrency.open_positions[i]['short']['exit'] = TradedCurrency.open_positions[i]['short']['stop loss'] 
        TradedCurrency.open_positions[i]['short']['actualised'] = True
        TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['long']['stop loss'] = TradedCurrency.open_positions[i]['short']['stop loss'] * (1+TradedCurrency.fee_rate)
        TradedCurrency.open_positions[i]['long']['actualised'] = True
        money_back = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
        money_back -= ((TradedCurrency.leverage - 1) / TradedCurrency.leverage * TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['exit'])
        TradedCurrency.capital += money_back
        TradedCurrency.capital -= TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['exit'] * TradedCurrency.fee_rate

    TradedCurrency.update_capital()
    return TradedCurrency


def long_stop_loss_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Update long stop loss contract & cancel long take profit contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['long']['stop loss'] = filled_contract
        TradedCurrency.contracts[i]['long']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['long']['exit'] = np.float(filled_contract['avgPrice'])
    else:
        TradedCurrency.open_positions[i]['long']['exit'] = np.float(TradedCurrency.open_positions[i]['long']['stop loss'])
        TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        money_back = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['exit']
        money_back -= ((TradedCurrency.leverage - 1) / TradedCurrency.leverage * TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry'])
        TradedCurrency.capital += money_back
        TradedCurrency.capital -= TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['exit'] * TradedCurrency.fee_rate

    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)

    # Update portfolio content according to Binance Futures account balance
    account_balance = Binance_API.get_futures_account_balance() 
    if not TradedCurrency.real_mode:
        account_balance['balance'] = TradedCurrency.capital
    df_balance = utils.read_csv(config.balance_path)
    df_balance = df_balance.append(account_balance, ignore_index=True)
    utils.dump_as_csv(df_balance, config.balance_path)
    return TradedCurrency


def short_stop_loss_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:    
        # Update short stop loss contract & cancel short take profit contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['short']['stop loss'] = filled_contract
        TradedCurrency.contracts[i]['short']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['short']['exit'] = np.float(filled_contract['avgPrice'])
    else:
        TradedCurrency.open_positions[i]['short']['exit'] =  np.float(TradedCurrency.open_positions[i]['short']['stop loss']) #close_price
        TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        money_back = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
        money_back -= ((TradedCurrency.leverage - 1) / TradedCurrency.leverage * TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['exit'])
        TradedCurrency.capital += money_back
        TradedCurrency.capital -= TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['exit'] * TradedCurrency.fee_rate
        
        # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)

    # Update portfolio content according to Binance Futures account balance
    account_balance = Binance_API.get_futures_account_balance() 
    if not TradedCurrency.real_mode:
        account_balance['balance'] = TradedCurrency.capital
    df_balance = utils.read_csv(config.balance_path)
    df_balance = df_balance.append(account_balance, ignore_index=True)
    utils.dump_as_csv(df_balance, config.balance_path)
    return TradedCurrency


def long_take_profit_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Update long take profit contract & cancel long stop loss contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        TradedCurrency.contracts[i]['long']['take profit'] = filled_contract
        TradedCurrency.contracts[i]['long']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['long']['exit'] = np.float(filled_contract['avgPrice'])
    else:
        TradedCurrency.open_positions[i]['long']['exit'] = np.float(TradedCurrency.open_positions[i]['long']['take profit']) #close_price
        TradedCurrency.open_positions[i]['long']['exit time'] = round(tm.time(), 3)
        money_back = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['exit']
        money_back -= ((TradedCurrency.leverage - 1) / TradedCurrency.leverage * TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry'])
        TradedCurrency.capital += money_back
        TradedCurrency.capital -= TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['exit'] * TradedCurrency.fee_rate
    
    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)

    # Update portfolio content according to Binance Futures account balance
    account_balance = Binance_API.get_futures_account_balance() 
    if not TradedCurrency.real_mode:
        account_balance['balance'] = TradedCurrency.capital
    df_balance = utils.read_csv(config.balance_path)
    df_balance = df_balance.append(account_balance, ignore_index=True)
    utils.dump_as_csv(df_balance, config.balance_path)
    return TradedCurrency


def short_take_profit_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Update short take profit contract & cancel short stop loss contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        TradedCurrency.contracts[i]['short']['take profit'] = filled_contract
        TradedCurrency.contracts[i]['short']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        TradedCurrency.open_positions[i]['short']['exit'] = np.float(filled_contract['avgPrice'])
    else:
        TradedCurrency.open_positions[i]['short']['exit'] = np.float(TradedCurrency.open_positions[i]['short']['take profit']) #close_price
        TradedCurrency.open_positions[i]['short']['exit time'] = round(tm.time(), 3)
        money_back = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
        money_back -= ((TradedCurrency.leverage - 1) / TradedCurrency.leverage * TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['exit'])
        TradedCurrency.capital += money_back
        TradedCurrency.capital -= TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['exit'] * TradedCurrency.fee_rate
    
    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)

    # Update portfolio content according to Binance Futures account balance
    account_balance = Binance_API.get_futures_account_balance() 
    if not TradedCurrency.real_mode:
        account_balance['balance'] = TradedCurrency.capital
    df_balance = utils.read_csv(config.balance_path)
    df_balance = df_balance.append(account_balance, ignore_index=True)
    utils.dump_as_csv(df_balance, config.balance_path)
    return TradedCurrency


def initiate_algorithm():
    """
    Check API keys are functional

    Get account balance

    Calculate maximal number of positions that can be opened at the same time
    based on Binance Futures base amount precision

    Instanciate Currency object

    Write files:
        order_ledger.csv (empty)
        trade_ledger.csv (empty)
        account_balance.csv (one line)
    
    Dump currency.pickle
    """
    logger.info('Initiating hedge mode algorithm')

    # Check API keys are functional & get account balance
    try:
        account_balance = Binance_API.get_futures_account_balance()
    except:
        logger.error('Error: Wrong API credentials. initiate_algorithm(): Error1')
        return
    
    # Calculate maximal number of positions
    available_balance = account_balance['availableBalance']
    if not config.REAL_MODE:
        available_balance = 1000
    price = Binance_API.get_price('BTCUSDT')
    usdt_per_position = 5 + price * 10**(-config.BASE_AMOUNT_PRECISION)
    max_nb_positions = np.min([5, int(available_balance//usdt_per_position//2)]) - 1

    # Instanciate Currency object
    TradedCurrency = models.Currency(max_nb_positions, available_balance)

    # Write csv files
    try:
        order_ledger = pd.DataFrame(columns=config.ORDER_LEDGER_COLUMNS)
        trade_ledger = pd.DataFrame(columns=config.TRADE_LEDGER_COLUMNS)
        balance = pd.DataFrame(columns=config.ACCOUNT_BALANCE_COLUMNS)
        balance.append(account_balance, ignore_index=True)
        file = 'order_ledger'
        utils.dump_as_csv(order_ledger, config.order_ledger_path)
        file = 'trade_ledger'
        utils.dump_as_csv(trade_ledger, config.trade_ledger_path)
        file = 'balance'
        utils.dump_as_csv(balance, config.balance_path)

        # Dump TradedCurrency.pickle
        file = 'TradedCurrency.pickle'
        utils.dump_as_pickle(TradedCurrency, config.TradedCurrency_path)
    except:
        logger.error(f'Error: Wrong measurements path {file} {config.TradedCurrency_path}')
        return

    logger.info('Hedge mode algorithm initiated')
    return


def continue_recurrent_algorithm():
    logger.info('Continue applying hedge mode strategy')

    TradedCurrency = utils.load_pickle(config.TradedCurrency_path)
    is_cross = check_api_keys_functional(TradedCurrency)
    check_margin_type(TradedCurrency, is_cross)    
    check_position_mode()
    if TradedCurrency.real_mode:
        Binance_API.change_initial_leverage(TradedCurrency.pair, TradedCurrency.leverage)
    
    # TradedCurrency.update_contracts()
    TradedCurrency.update_capital()
    ohlc = TradedCurrency.load_latest_ohlc()

    # Every minute or so, we need to look if a conditional contract has been activated
    # Therefore, we will be able to update stop loss and take profit levels more accurately
    for i in range(0, TradedCurrency.max_open_positions):
        print(f"Evaluating position {i}")
        if TradedCurrency.open_positions[i] != None:
            print('Tried sell case 1')
            # Case: long stop loss activated
            if TradedCurrency.open_positions[i]['long']['actualised'] == False:
                print('Step A passed')
                if TradedCurrency.is_stop_loss_activated(i, 'long'):
                    print('Step B passed')
                    TradedCurrency = first_long_stop_loss_activation(TradedCurrency, i)
        
        if TradedCurrency.open_positions[i] != None:
            print('Tried sell case 2')
            # Case: short stop loss activated
            if TradedCurrency.open_positions[i]['short']['actualised'] == False:
                print('Step A passed')
                if TradedCurrency.is_stop_loss_activated(i, 'short'):
                    print('Step B passed')
                    TradedCurrency = first_short_stop_loss_activation(TradedCurrency, i)
        
        if TradedCurrency.open_positions[i] != None:
            print('Tried sell case 3')
            # Case: closing actualised positions on long stop loss activation
            if TradedCurrency.open_positions[i]['long']['actualised'] == True:
                print('Step A passed')
                if TradedCurrency.is_stop_loss_activated(i, 'long'):
                    print('Step B passed')
                    TradedCurrency = long_stop_loss_closing(TradedCurrency, i)
                    
        if TradedCurrency.open_positions[i] != None:
            print('Tried sell case 4')
            # Case: closing actualised positions on short stop loss activation
            if TradedCurrency.open_positions[i]['short']['actualised'] == True:
                print('Step A passed')
                if TradedCurrency.is_stop_loss_activated(i, 'short'):
                    print('Step B passed')
                    TradedCurrency = short_stop_loss_closing(TradedCurrency, i)

        if TradedCurrency.open_positions[i] != None:
            print('Tried sell case 5')
            # Case: closing actualised positions on long take profit activation
            if TradedCurrency.open_positions[i]['long']['actualised'] == True:
                print('Step A passed')
                if TradedCurrency.is_take_profit_activated(i, 'long'):
                    print('Step B passed')
                    TradedCurrency = long_take_profit_closing(TradedCurrency, i)

        if TradedCurrency.open_positions[i] != None: 
            print('Tried sell case 6')   
            # Case: closing actualised positions on short take profit activation
            if TradedCurrency.open_positions[i]['short']['actualised'] == True:
                print('Step A passed')
                if TradedCurrency.is_take_profit_activated(i, 'short'):
                    print('Step B passed')
                    TradedCurrency = short_take_profit_closing(TradedCurrency, i)

    print('Minutely process executed')

    # Then we look if a position can be opened every time the server time reaches next_timestamp
    server_time = Binance_API.get_server_time() / 1000
    if server_time >= TradedCurrency.next_timestamp.timestamp() - 30:
        wait_for_next_timestamp(TradedCurrency)

        # Define opening trades criteria
        ohlc = TradedCurrency.load_latest_ohlc()
        slow_2, fast_2 = ohlc['ema_slow'].iloc[len(ohlc)-2], ohlc['ema_fast'].iloc[len(ohlc)-2]
        slow_1, fast_1 = ohlc['ema_slow'].iloc[len(ohlc)-1], ohlc['ema_fast'].iloc[len(ohlc)-1]

        crossover = fast_2 < slow_2 and fast_1 >= slow_1
        crossunder = fast_2 > slow_2 and fast_1 <= slow_1

        if (crossover or crossunder) and TradedCurrency.n_open_positions < TradedCurrency.max_open_positions:
            available_position = TradedCurrency.find_available_position()
            if available_position == None:
                logger.error('Error: Currency.find_available_position() returned None.')
                return
            # Caclulate amount for the new trade
            amount = np.floor(TradedCurrency.capital / (TradedCurrency.max_open_positions - TradedCurrency.n_open_positions) * 10**(config.BASE_AMOUNT_PRECISION))
            amount /= 10**(config.BASE_AMOUNT_PRECISION)
            # Place contracts and open positions
            if TradedCurrency.real_mode:
                initial_orders = TradedCurrency.prepare_initial_orders()
                initial_contracts = TradedCurrency.place_orders_simultaneously(initial_orders)
                initial_contracts[0] = Binance_API.query_order(TradedCurrency.pair, initial_contracts[0]['orderId'])
                initial_contracts[1] = Binance_API.query_order(TradedCurrency.pair, initial_contracts[1]['orderId'])
                TradedCurrency.contracts[available_position]['long']['order'] = initial_contracts[0] if initial_contracts[0]['positionSide'] == 'LONG' else initial_contracts[1]
                TradedCurrency.contracts[available_position]['short']['order'] = initial_contracts[0] if initial_contracts[0]['positionSide'] == 'SHORT' else initial_contracts[1]
                initial_activation_orders = TradedCurrency.prepare_initial_activation_orders(available_position)
                initial_activation_contracts = TradedCurrency.place_orders_simultaneously(initial_activation_orders)
                
                for contract in initial_activation_contracts:
                    if contract['positionSide'] == 'LONG' and contract['type'] == 'TAKE_PROFIT_MARKET':
                        TradedCurrency.contracts[available_position]['long']['take profit'] = contract
                    elif contract['positionSide'] == 'LONG' and contract['type'] == 'STOP_MARKET':
                        TradedCurrency.contracts[available_position]['long']['stop loss'] = contract
                    if contract['positionSide'] == 'SHORT' and contract['type'] == 'TAKE_PROFIT_MARKET':
                        TradedCurrency.contracts[available_position]['short']['take profit'] = contract
                    elif contract['positionSide'] == 'SHORT' and contract['type'] == 'STOP_MARKET':
                        TradedCurrency.contracts[available_position]['short']['stop loss'] = contract
                    
            TradedCurrency.set_positions(available_position)

        # Update portfolio content according to Binance Futures account balance
        account_balance = Binance_API.get_futures_account_balance() 
        if not TradedCurrency.real_mode:
            account_balance['balance'] = TradedCurrency.capital
        df_balance = utils.read_csv(config.balance_path)
        df_balance = df_balance.append(account_balance, ignore_index=True)
        utils.dump_as_csv(df_balance, config.balance_path)

        # Update next_timestamp
        TradedCurrency.next_timestamp += TradedCurrency.timedelta
        print('Quarterly process executed')
    
    TradedCurrency.update_capital()
    utils.dump_as_pickle(TradedCurrency, config.TradedCurrency_path)

    return