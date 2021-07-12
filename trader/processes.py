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
            logger.info(f'Sleep for {sleep_time} seconds')
            tm.sleep(sleep_time)
            server_time = Binance_API.get_server_time() / 1000
            counter += 1
    except:
        error_msg = f'Error: Either cannot get server time (API overloaded) or next timestamp never reached'
        error_msg += f" Server time: {pd.Timestamp(server_time, unit='s')}"
        error_msg += f" Next timestamp: {TradedCurrency.next_timestamp}"
        error_msg += ' [continue_recurrent_algorithm: error4]'
        logger.error(error_msg)
        return
    return


def first_long_stop_loss_activation(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Contract is filled => update : long position (exit, exit time, actualised) & short position (stop loss, actualised)
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['long']['stop loss'] = filled_contract
        TradedCurrency.open_positions[i]['long']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['long']['exit'] = filled_contract['avgPrice']
        TradedCurrency.open_positions[i]['long']['actualised'] = True
        TradedCurrency.contracts[i]['long']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        # Cancel previous short contract stop loss & open a new one (with stop at entry but unchanged profit)
        TradedCurrency.contracts[i]['short']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        order_settings = {
            'symbol': TradedCurrency.pair,
            'side': 'BUY',
            'positionSide': 'SHORT',
            'type': 'STOP_MARKET',
            'quantity': str(TradedCurrency.contracts[i]['short']['order']['executedQty']),
            'stopPrice': str(np.float(TradedCurrency.open_positions[i]['long']['exit'])) # + 10
        }
        try:
            TradedCurrency.contracts[i]['short']['stop loss'] = TradedCurrency.place_single_order(order_settings)
        except:
            TradedCurrency.contracts[i]['short']['stop loss']['status'] = 'immediately activated'
        TradedCurrency.open_positions[i]['short']['stop loss'] = TradedCurrency.contracts[i]['short']['stop loss']['price']
        TradedCurrency.open_positions[i]['short']['actualised'] = True
    else:
        TradedCurrency.open_positions[i]['long']['exit'] = TradedCurrency.open_positions[i]['long']['stop loss']
        TradedCurrency.open_positions[i]['long']['actualised'] = True
        TradedCurrency.open_positions[i]['long']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['short']['stop loss'] = TradedCurrency.open_positions[i]['long']['stop loss']
        TradedCurrency.open_positions[i]['short']['actualised'] = True
    return TradedCurrency


def first_short_stop_loss_activation(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Contract is filled => update : short position (exit, exit time, actualised) & long position (stop loss, actualised)
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['short']['stop loss'] = filled_contract
        TradedCurrency.open_positions[i]['short']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['short']['exit'] = filled_contract['avgPrice']
        TradedCurrency.open_positions[i]['short']['actualised'] = True
        TradedCurrency.contracts[i]['short']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        # Cancel previous short contract stop loss & open a new one (with stop at entry but unchanged profit)
        TradedCurrency.contracts[i]['long']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        order_settings = {
            'symbol': TradedCurrency.pair,
            'side': 'SELL',
            'positionSide': 'LONG',
            'type': 'STOP_MARKET',
            'quantity': str(TradedCurrency.contracts[i]['long']['order']['executedQty']),
            'stopPrice': str(np.float(TradedCurrency.open_positions[i]['short']['exit'])) # - 10
        }
        try:
            TradedCurrency.contracts[i]['long']['stop loss'] = TradedCurrency.place_single_order(order_settings)
        except:
            TradedCurrency.contracts[i]['long']['stop loss']['status'] = 'immediately activated'
        TradedCurrency.open_positions[i]['long']['stop loss'] = TradedCurrency.contracts[i]['long']['stop loss']['price']
        TradedCurrency.open_positions[i]['long']['actualised'] = True
    else:
        TradedCurrency.open_positions[i]['short']['exit'] = TradedCurrency.open_positions[i]['short']['stop loss'] 
        TradedCurrency.open_positions[i]['short']['actualised'] = True
        TradedCurrency.open_positions[i]['short']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['long']['stop loss'] = TradedCurrency.open_positions[i]['short']['stop loss'] 
        TradedCurrency.open_positions[i]['long']['actualised'] = True
    return TradedCurrency


def long_stop_loss_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Update long stop loss contract & cancel long take profit contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['long']['stop loss'] = filled_contract
        TradedCurrency.contracts[i]['long']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['long']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['long']['exit'] = filled_contract['avgPrice']
    else:
        TradedCurrency.open_positions[i]['long']['exit'] = TradedCurrency.open_positions[i]['long']['stop loss'] 
        TradedCurrency.open_positions[i]['long']['exit time'] = TradedCurrency.next_timestamp.timestamp()
    
    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)
    return TradedCurrency


def short_stop_loss_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:    
        # Update short stop loss contract & cancel short take profit contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        TradedCurrency.contracts[i]['short']['stop loss'] = filled_contract
        TradedCurrency.contracts[i]['short']['take profit'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['short']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['short']['exit'] = filled_contract['avgPrice']
    else:
        TradedCurrency.open_positions[i]['short']['exit'] =  TradedCurrency.open_positions[i]['short']['stop loss'] #close_price
        TradedCurrency.open_positions[i]['short']['exit time'] =  TradedCurrency.next_timestamp.timestamp()
    
    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)
    return TradedCurrency


def long_take_profit_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Update long take profit contract & cancel long stop loss contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['take profit']['orderId'])
        TradedCurrency.contracts[i]['long']['take profit'] = filled_contract
        TradedCurrency.contracts[i]['long']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['long']['stop loss']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['long']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['long']['exit'] = filled_contract['avgPrice']
    else:
        TradedCurrency.open_positions[i]['long']['exit'] = TradedCurrency.open_positions[i]['long']['take profit'] #close_price
        TradedCurrency.open_positions[i]['long']['exit time'] = TradedCurrency.next_timestamp.timestamp()
    
    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)
    return TradedCurrency


def short_take_profit_closing(TradedCurrency, i):
    if TradedCurrency.real_mode:
        # Update short take profit contract & cancel short stop loss contract
        filled_contract = Binance_API.query_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['take profit']['orderId'])
        TradedCurrency.contracts[i]['short']['take profit'] = filled_contract
        TradedCurrency.contracts[i]['short']['stop loss'] = Binance_API.cancel_order(TradedCurrency.pair, TradedCurrency.contracts[i]['short']['stop loss']['orderId'])
        # Update open_positions
        TradedCurrency.open_positions[i]['short']['exit time'] = TradedCurrency.next_timestamp.timestamp()
        TradedCurrency.open_positions[i]['short']['exit'] = filled_contract['avgPrice']
    else:
        TradedCurrency.open_positions[i]['short']['exit'] = TradedCurrency.open_positions[i]['short']['take profit'] #close_price
        TradedCurrency.open_positions[i]['short']['exit time'] = TradedCurrency.next_timestamp.timestamp()
    
    # Store closed contracts and positions in order_ledger & trade_ledger
    TradedCurrency.update_ledgers(i)
    TradedCurrency.close_position(i)
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
    Binance_API.change_initial_leverage(TradedCurrency.pair, TradedCurrency.leverage)
    
    ohlc = TradedCurrency.load_latest_ohlc()

    # Every minute or so, we need to look if a conditional contract has been activated
    # Therefore, we will be able to update stop loss and take profit levels more accurately
    for i in range(0, TradedCurrency.max_open_positions):
        if TradedCurrency.open_positions[i] != None:
            # Case: long stop loss activated
            if (TradedCurrency.open_positions[i]['long']['actualised'] == False and TradedCurrency.is_stop_loss_activated(i, 'long', ohlc=ohlc)):
                TradedCurrency = first_long_stop_loss_activation(TradedCurrency, i)

            # Case: short stop loss activated
            elif (TradedCurrency.open_positions[i]['short']['actualised'] == False and TradedCurrency.is_stop_loss_activated(i, 'short', ohlc=ohlc)):
                TradedCurrency = first_short_stop_loss_activation(TradedCurrency, i)
            
            # Case: closing actualised positions on long stop loss activation
            elif (TradedCurrency.open_positions[i]['long']['actualised'] == True and TradedCurrency.is_stop_loss_activated(i, 'long', ohlc=ohlc)):
                TradedCurrency = long_stop_loss_closing(TradedCurrency, i)

            # Case: closing actualised positions on short stop loss activation
            elif (TradedCurrency.open_positions[i]['short']['actualised'] == True and TradedCurrency.is_stop_loss_activated(i, 'short', ohlc=ohlc)):
                TradedCurrency = short_stop_loss_closing(TradedCurrency, i)

            # Case: closing actualised positions on long take profit activation
            elif (TradedCurrency.open_positions[i]['long']['actualised'] == True and TradedCurrency.is_take_profit_activated(i, 'long', ohlc=ohlc)):
                TradedCurrency = long_take_profit_closing(TradedCurrency, i)

            # Case: closing actualised positions on short take profit activation
            elif (TradedCurrency.open_positions[i]['short']['actualised'] == True and TradedCurrency.is_take_profit_activated(i, 'short', ohlc=ohlc)):
                TradedCurrency = short_take_profit_closing(TradedCurrency, i)

    print('Minutely process executed')

    # Then we look if a position can be opened every time the server time reaches next_timestamp
    server_time = Binance_API.get_server_time() / 1000
    if server_time < TradedCurrency.next_timestamp.timestamp() and server_time + 60 >= TradedCurrency.next_timestamp.timestamp():
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
        utils.dump_as_pickle(TradedCurrency, config.TradedCurrency_path)

        print('Hourly process executed')

    return