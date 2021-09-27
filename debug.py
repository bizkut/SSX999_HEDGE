# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import numpy as np
import numpy as np
import pandas as pd
import pickle
import logging
import os
from trader import Binance_API, config, env, models, processes, utils

log_path = 'measurements/debug.log'

logger = logging.getLogger('SSX999 HEDGER')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(log_path)
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

def reset_logs():
    logging.shutdown()
    os.remove('measurements/debug.log')
    return


def initiate_algorithm_debug():
    reset_logs()
    logger.info("_________________________\nDebugging initiate_algorithm()\n_________________________")
    
    try:
        account_balance = Binance_API.get_futures_account_balance()
        logger.info("\nAPI request done. account_balance obtained.")
    except:
        logger.info('\nError: Wrong API credentials. initiate_algorithm(): Error1')
        return
    
    # Calculate maximal number of positions
    available_balance = account_balance['availableBalance']
    logger.info(f"\navailable balance: {available_balance}")
    price = Binance_API.get_price('BTCUSDT')
    logger.info(f"\nprice: {price}")
    usdt_per_position = 5 + price * 10**(-config.BASE_AMOUNT_PRECISION)
    logger.info(f"\nusdt_per_position: {usdt_per_position}")
    max_nb_positions = np.min([5, int(available_balance//usdt_per_position//2)]) - 1
    logger.info(f"\nmax_nb_positions: {max_nb_positions}")

    # Instanciate Currency object
    TradedCurrency = models.Currency(max_nb_positions, available_balance)
    logger.info("\nTradedCurrency")
    logger.info(f"\tnext_timestamp: {TradedCurrency.next_timestamp}")
    logger.info(f"\tcapital: {TradedCurrency.capital}")
    logger.info(f"\tleverage: {TradedCurrency.leverage}")
    logger.info(f"\tmax_open_position: {TradedCurrency.max_open_positions}")
    logger.info(f"\tn_open_positions: {TradedCurrency.n_open_positions}")
    logger.info(f"\topen_positions: {TradedCurrency.open_positions}")
    logger.info(f"\tcontracts: {TradedCurrency.contracts}")

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
        logger.info(f'\nError: Wrong measurements path {file} {config.TradedCurrency_path}')
        return

    logger.info("\n\ninitiate_algorithm: debug done. All variables displayed.")
    return


def cra_stage0():
    reset_logs()
    logger.info("_________________________\nDebugging continue_recurrent_algorithm()-->stage0\n_________________________")

    logger.info("\nResetting measurements files")
    try:
        os.remove(config.TradedCurrency_path)
        os.remove(config.balance_path)
        os.remove(config.order_ledger_path)
        os.remove(config.trade_ledger_path)
        initiate_algorithm_debug()
    except:
        logger.info("No measurements files to reset")
        initiate_algorithm_debug()

    logger.info('Continue applying hedge mode strategy')

    TradedCurrency = utils.load_pickle(config.TradedCurrency_path)
    is_cross = processes.check_api_keys_functional(TradedCurrency)
    processes.check_margin_type(TradedCurrency, is_cross)    
    processes.check_position_mode()
    if TradedCurrency.real_mode:
        Binance_API.change_initial_leverage(TradedCurrency.pair, TradedCurrency.leverage)
    
    logger.info(f"\ncapital 1: {TradedCurrency.capital}")
    TradedCurrency.update_capital()
    logger.info(f"\ncapital 2: {TradedCurrency.capital}")
    ohlc = TradedCurrency.load_latest_ohlc()
    # logger.info(f"\nOHLC data: {ohlc.head(30)}")
    logger.info(f"\nLatest OHLC candlestick: {pd.Timestamp(ohlc['open_time'].iloc[-1], unit='ms')}")
    logger.info("\n\ncontinue_recurrent_algorithm: debug done. All variables printed")
    logger.info("Returning TradedCurrency, ohlc")
    return TradedCurrency, ohlc


def cra_open_positions(real_mode=False):
    reset_logs()
    logger.info("_________________________\nDebugging continue_recurrent_algorithm()-->stage0\n_________________________")
    TradedCurrency, ohlc = cra_stage0()
        
    # Define opening trades criteria
    slow_2, fast_2 = ohlc['ema_slow'].iloc[len(ohlc)-2], ohlc['ema_fast'].iloc[len(ohlc)-2]
    slow_1, fast_1 = ohlc['ema_slow'].iloc[len(ohlc)-1], ohlc['ema_fast'].iloc[len(ohlc)-1]

    crossover = fast_2 < slow_2 and fast_1 >= slow_1
    crossunder = fast_2 > slow_2 and fast_1 <= slow_1

    crossover, crossunder = True, True
    
    TradedCurrency.real_mode = real_mode
    logger.info("Contracts & positions reset")
    logger.info(f"Initial next_timestamp: {TradedCurrency.next_timestamp}")

    if (crossover or crossunder) and TradedCurrency.n_open_positions < TradedCurrency.max_open_positions:
        available_position = TradedCurrency.find_available_position()
        logger.info(f"available_position: {available_position}")
        if available_position == None:
            logger.info('Error: Currency.find_available_position() returned None.')
            return
        # Caclulate amount for the new trade
        amount = np.floor(TradedCurrency.capital / (TradedCurrency.max_open_positions - TradedCurrency.n_open_positions) * 10**(config.BASE_AMOUNT_PRECISION))
        amount /= 10**(config.BASE_AMOUNT_PRECISION)
        logger.info(f"amount: {amount}")
        logger.info(f"IS REAL MODE ? --> {TradedCurrency.real_mode}")
        # Place contracts and open positions
        if TradedCurrency.real_mode:
            logger.info('\nReal mode logic started')

            initial_orders = TradedCurrency.prepare_initial_orders()
            logger.info(f"initial_orders:")
            for initial_order in initial_orders:
                logger.info("\tinitial order")
                for key in initial_order.keys():
                    logger.info(f"\t\t{key}: {initial_order[key]}")
            
            initial_contracts = TradedCurrency.place_orders_simultaneously(initial_orders)
            logger.info(f"initial contracts:")
            for initial_contract in initial_contracts:
                logger.info("\tinitial_contract")
                for key in initial_contract.keys():
                    logger.info(f"\t\t{key}: {initial_contract[key]}")

            initial_contracts[0] = Binance_API.query_order(TradedCurrency.pair, initial_contracts[0]['orderId'])
            initial_contracts[1] = Binance_API.query_order(TradedCurrency.pair, initial_contracts[1]['orderId'])
            TradedCurrency.contracts[available_position]['long']['order'] = initial_contracts[0] if initial_contracts[0]['positionSide'] == 'LONG' else initial_contracts[1]
            TradedCurrency.contracts[available_position]['short']['order'] = initial_contracts[0] if initial_contracts[0]['positionSide'] == 'SHORT' else initial_contracts[1]
            initial_activation_orders = TradedCurrency.prepare_initial_activation_orders(available_position)
            logger.info(f"initial activation orders:")
            for initial_activation_order in initial_activation_orders:
                logger.info("\tinitial_activation_order")
                for key in initial_activation_order.keys():
                    logger.info(f"\t\t{key}: {initial_activation_order[key]}")


            initial_activation_contracts = TradedCurrency.place_orders_simultaneously(initial_activation_orders)
            logger.info(f"initial activation contracts:")
            for initial_activation_contract in initial_activation_contracts:
                logger.info("\tinitial_activation_contract")
                for key in initial_activation_contract.keys():
                    logger.info(f"\t\t{key}: {initial_activation_contract[key]}")
            
            for contract in initial_activation_contracts:
                if contract['positionSide'] == 'LONG' and contract['type'] == 'TAKE_PROFIT_MARKET':
                    TradedCurrency.contracts[available_position]['long']['take profit'] = contract
                elif contract['positionSide'] == 'LONG' and contract['type'] == 'STOP_MARKET':
                    TradedCurrency.contracts[available_position]['long']['stop loss'] = contract
                if contract['positionSide'] == 'SHORT' and contract['type'] == 'TAKE_PROFIT_MARKET':
                    TradedCurrency.contracts[available_position]['short']['take profit'] = contract
                elif contract['positionSide'] == 'SHORT' and contract['type'] == 'STOP_MARKET':
                    TradedCurrency.contracts[available_position]['short']['stop loss'] = contract
            logger.info('\nReal mode logic ended')

        logger.info("Setting positions")
        TradedCurrency.set_positions(available_position)
        logger.info(f"real_mode: {TradedCurrency.real_mode}")
        logger.info("open_positions:")
        for idx in range(TradedCurrency.max_open_positions):
            if TradedCurrency.open_positions[idx] != None:
                for position in TradedCurrency.open_positions[idx].keys():
                    logger.info(f"\t{position}")
                    for item in TradedCurrency.open_positions[idx][position].keys():
                        logger.info(f"\t\t{item}: {TradedCurrency.open_positions[idx][position][item]}")
        logger.info("contracts:")
        for idx in range(TradedCurrency.max_open_positions):
                for side in ['long', 'short']:
                    logger.info(f'\t{side}:')
                    for type in ['order', 'stop loss', 'take profit']:
                        logger.info(f"\t\t{type}:")
                        if TradedCurrency.contracts[idx][side][type] != None:
                            for item in TradedCurrency.contracts[idx][side][type].keys():
                                logger.info(f"\t\t\t{item}: {TradedCurrency.contracts[idx][side][type][item]}")

    # Update portfolio content according to Binance Futures account balance
    account_balance = Binance_API.get_futures_account_balance() 
    if not TradedCurrency.real_mode:
        account_balance['balance'] = TradedCurrency.capital
    df_balance = utils.read_csv(config.balance_path)
    df_balance = df_balance.append(account_balance, ignore_index=True)
    utils.dump_as_csv(df_balance, config.balance_path)

    # Update next_timestamp
    TradedCurrency.next_timestamp += TradedCurrency.timedelta
    logger.info(f"Final next_timestamp: {TradedCurrency.next_timestamp}")
    logger.info(f"Final capital: {TradedCurrency.capital}")

    TradedCurrency.update_capital()
    utils.dump_as_pickle(TradedCurrency, config.TradedCurrency_path)
    
    logger.info("continue_recurrent_algorithm (opening positions): debug done. All variables printed")
    logger.info("Returning TradedCurrency")

    if TradedCurrency.real_mode:
        for idx in range(TradedCurrency.max_open_positions):
            if TradedCurrency.contracts[idx]['long']['order'] != None:
                long_order = {
                    'symbol': TradedCurrency.pair,
                    'side': 'SELL',
                    'positionSide': 'LONG',
                    'type': 'MARKET',
                    'quantity': str(TradedCurrency.contracts[idx]['long']['order']['executedQty'])
                }
                short_order = {
                    'symbol': TradedCurrency.pair,
                    'side': 'BUY',
                    'positionSide': 'SHORT',
                    'type': 'MARKET',
                    'quantity': str(TradedCurrency.contracts[idx]['short']['order']['executedQty'])
                }

                TradedCurrency.place_orders_simultaneously([long_order, short_order])

                for side in ['long', 'short']:
                    for type in ['stop loss', 'take profit']:
                        order_id = TradedCurrency.contracts[idx][side][type]['orderId']
                        TradedCurrency.cancel_order(order_id)

    return TradedCurrency


def cra_long_stop_loss_activated(real_mode=False):
    reset_logs()
    logger.info("_________________________\nDebugging continue_recurrent_algorithm()-->long_stop_loss_activated\n_________________________")
    
    TradedCurrency = cra_open_positions(real_mode=real_mode)
    logger.info("\n_________________________________________________")
    logger.info("\n               POSITION OPENED                   ")
    logger.info("\n_________________________________________________")
    
    previous_capital = TradedCurrency.capital

    for i in range(0, TradedCurrency.max_open_positions):
        if TradedCurrency.open_positions[i] != None:
            # Case: long stop loss activated
            if TradedCurrency.open_positions[i]['long']['actualised'] == False:
                if True:# TradedCurrency.is_stop_loss_activated(i, 'long', ohlc=ohlc):
                    long_position_size = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry']
                    short_position_size = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
                    TradedCurrency = processes.first_long_stop_loss_activation(TradedCurrency, i)
                    
                    logger.info('\nActivation: adjusting positions')
                    logger.info("\nTradedCurrency-->open_positions[i]")
                    logger.info(f"\t[LONG] entry time: {TradedCurrency.open_positions[i]['long']['entry time']}")
                    logger.info(f"\t[LONG] exit time: {TradedCurrency.open_positions[i]['long']['exit time']}")
                    logger.info(f"\t[LONG] id: {TradedCurrency.open_positions[i]['long']['id']}")
                    logger.info(f"\t[LONG] entry: {TradedCurrency.open_positions[i]['long']['entry']}")
                    logger.info(f"\t[LONG] exit: {TradedCurrency.open_positions[i]['long']['exit']}")
                    logger.info(f"\t[LONG] qty: {TradedCurrency.open_positions[i]['long']['qty']}")
                    logger.info(f"\t[LONG] leverage: {TradedCurrency.open_positions[i]['long']['leverage']}")
                    logger.info(f"\t[LONG] stop loss: {TradedCurrency.open_positions[i]['long']['stop loss']}")
                    logger.info(f"\t[LONG] take profit: {TradedCurrency.open_positions[i]['long']['take profit']}")
                    logger.info(f"\t[LONG] actualised: {TradedCurrency.open_positions[i]['long']['actualised']}")
                    logger.info("\t--------------------------------------------")
                    logger.info(f"\t[SHORT] entry time: {TradedCurrency.open_positions[i]['short']['entry time']}")
                    logger.info(f"\t[SHORT] exit time: {TradedCurrency.open_positions[i]['short']['exit time']}")
                    logger.info(f"\t[SHORT] id: {TradedCurrency.open_positions[i]['short']['id']}")
                    logger.info(f"\t[SHORT] entry: {TradedCurrency.open_positions[i]['short']['entry']}")
                    logger.info(f"\t[SHORT] exit: {TradedCurrency.open_positions[i]['short']['exit']}")
                    logger.info(f"\t[SHORT] qty: {TradedCurrency.open_positions[i]['short']['qty']}")
                    logger.info(f"\t[SHORT] leverage: {TradedCurrency.open_positions[i]['short']['leverage']}")
                    logger.info(f"\t[SHORT] stop loss: {TradedCurrency.open_positions[i]['short']['stop loss']}")
                    logger.info(f"\t[SHORT] take profit: {TradedCurrency.open_positions[i]['short']['take profit']}")
                    logger.info(f"\t[SHORT] actualised: {TradedCurrency.open_positions[i]['short']['actualised']}")

                    logger.info("\nChecking position adjustment done correctly")
                    logger.info(f"[LONG] non-zero exit time: {TradedCurrency.open_positions[i]['long']['exit time'] != 0}")
                    long_short_actualised = TradedCurrency.open_positions[i]['long']['actualised'] == TradedCurrency.open_positions[i]['short']['actualised'] and TradedCurrency.open_positions[i]['long']['actualised'] == True
                    logger.info(f"\nlong & short actualised: {long_short_actualised}")
                    long_exit_stoploss = TradedCurrency.open_positions[i]['long']['exit'] == TradedCurrency.open_positions[i]['long']['stop loss']
                    logger.info(f"[LONG] exit == stop loss: {long_exit_stoploss}")
                    long_pnl = round((TradedCurrency.open_positions[i]['long']['exit'] / TradedCurrency.open_positions[i]['long']['entry'] - 1)*100, 2)
                    logger.info(f"[LONG] pnl: {long_pnl}%")
                    logger.info(f"[SHORT] zero exit time: {TradedCurrency.open_positions[i]['short']['exit time'] == 0}")
                    short_updated_stoploss = TradedCurrency.open_positions[i]['short']['stop loss'] == TradedCurrency.open_positions[i]['long']['stop loss']
                    logger.info(f"[SHORT] updated stop loss: {short_updated_stoploss}")

                    logger.info(f"\nPrevious capital: {previous_capital} USDT")
                    logger.info(f"New capital: {TradedCurrency.capital} USDT")
                    logger.info(f"Long position size: {long_position_size} USDT")
                    logger.info(f"Short position size: {short_position_size} USDT")

        
    logger.info("continue_recurrent_algorithm (long stop loss activation): debug done. All variables printed")
    logger.info("Returning TradedCurrency")
    return TradedCurrency             


def cra_short_stop_loss_activated(real_mode=False):
    reset_logs()
    logger.info("_________________________\nDebugging continue_recurrent_algorithm()-->short_stop_loss_activated\n_________________________")
    
    TradedCurrency = cra_open_positions(real_mode=real_mode)
    logger.info("\n_________________________________________________")
    logger.info("\n               POSITION OPENED                   ")
    logger.info("\n_________________________________________________")
    
    previous_capital = TradedCurrency.capital

    for i in range(0, TradedCurrency.max_open_positions):
        if TradedCurrency.open_positions[i] != None:
            # Case: long stop loss activated
            if TradedCurrency.open_positions[i]['short']['actualised'] == False:
                if True:# TradedCurrency.is_stop_loss_activated(i, 'long', ohlc=ohlc):
                    long_position_size = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry']
                    short_position_size = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
                    TradedCurrency = processes.first_short_stop_loss_activation(TradedCurrency, i)
                    
                    logger.info('\nActivation: adjusting positions')
                    logger.info("\nTradedCurrency-->open_positions[i]")
                    logger.info(f"\t[LONG] entry time: {TradedCurrency.open_positions[i]['long']['entry time']}")
                    logger.info(f"\t[LONG] exit time: {TradedCurrency.open_positions[i]['long']['exit time']}")
                    logger.info(f"\t[LONG] id: {TradedCurrency.open_positions[i]['long']['id']}")
                    logger.info(f"\t[LONG] entry: {TradedCurrency.open_positions[i]['long']['entry']}")
                    logger.info(f"\t[LONG] exit: {TradedCurrency.open_positions[i]['long']['exit']}")
                    logger.info(f"\t[LONG] qty: {TradedCurrency.open_positions[i]['long']['qty']}")
                    logger.info(f"\t[LONG] leverage: {TradedCurrency.open_positions[i]['long']['leverage']}")
                    logger.info(f"\t[LONG] stop loss: {TradedCurrency.open_positions[i]['long']['stop loss']}")
                    logger.info(f"\t[LONG] take profit: {TradedCurrency.open_positions[i]['long']['take profit']}")
                    logger.info(f"\t[LONG] actualised: {TradedCurrency.open_positions[i]['long']['actualised']}")
                    logger.info("\t--------------------------------------------")
                    logger.info(f"\t[SHORT] entry time: {TradedCurrency.open_positions[i]['short']['entry time']}")
                    logger.info(f"\t[SHORT] exit time: {TradedCurrency.open_positions[i]['short']['exit time']}")
                    logger.info(f"\t[SHORT] id: {TradedCurrency.open_positions[i]['short']['id']}")
                    logger.info(f"\t[SHORT] entry: {TradedCurrency.open_positions[i]['short']['entry']}")
                    logger.info(f"\t[SHORT] exit: {TradedCurrency.open_positions[i]['short']['exit']}")
                    logger.info(f"\t[SHORT] qty: {TradedCurrency.open_positions[i]['short']['qty']}")
                    logger.info(f"\t[SHORT] leverage: {TradedCurrency.open_positions[i]['short']['leverage']}")
                    logger.info(f"\t[SHORT] stop loss: {TradedCurrency.open_positions[i]['short']['stop loss']}")
                    logger.info(f"\t[SHORT] take profit: {TradedCurrency.open_positions[i]['short']['take profit']}")
                    logger.info(f"\t[SHORT] actualised: {TradedCurrency.open_positions[i]['short']['actualised']}")

                    logger.info("\nChecking position adjustment done correctly")
                    logger.info(f"[SHORT] non-zero exit time: {TradedCurrency.open_positions[i]['short']['exit time'] != 0}")
                    long_short_actualised = TradedCurrency.open_positions[i]['long']['actualised'] == TradedCurrency.open_positions[i]['short']['actualised'] and TradedCurrency.open_positions[i]['long']['actualised'] == True
                    logger.info(f"\nlong & short actualised: {long_short_actualised}")
                    short_exit_stoploss = TradedCurrency.open_positions[i]['short']['exit'] == TradedCurrency.open_positions[i]['short']['stop loss']
                    logger.info(f"[SHORT] exit == stop loss: {short_exit_stoploss}")
                    short_pnl = round((TradedCurrency.open_positions[i]['short']['entry'] / TradedCurrency.open_positions[i]['short']['exit'] - 1)*100, 2)
                    logger.info(f"[SHORT] pnl: {short_pnl}%")
                    logger.info(f"[LONG] zero exit time: {TradedCurrency.open_positions[i]['long']['exit time'] == 0}")
                    long_updated_stoploss = TradedCurrency.open_positions[i]['long']['stop loss'] == TradedCurrency.open_positions[i]['short']['stop loss']
                    logger.info(f"[LONG] updated stop loss: {long_updated_stoploss}")

                    logger.info(f"\nPrevious capital: {previous_capital} USDT")
                    logger.info(f"New capital: {TradedCurrency.capital} USDT")
                    logger.info(f"Long position size: {long_position_size} USDT")
                    logger.info(f"Short position size: {short_position_size} USDT")

        
    logger.info("continue_recurrent_algorithm (long stop loss activation): debug done. All variables printed")
    logger.info("Returning TradedCurrency")
    return TradedCurrency


def cra_long_stop_loss_closing(real_mode=False):
    reset_logs()
    logger.info("_________________________\nDebugging continue_recurrent_algorithm()-->long_stop_loss_closing\n_________________________")

    TradedCurrency = cra_short_stop_loss_activated(real_mode=real_mode)
    logger.info("\n_________________________________________________")
    logger.info("\n           LONG STOP LOSS ACTIVATED              ")
    logger.info("\n_________________________________________________")
    
    previous_capital = TradedCurrency.capital


    for i in range(0, TradedCurrency.max_open_positions):        
        if TradedCurrency.open_positions[i] != None:
            # Case: closing actualised positions on long stop loss activation
            if TradedCurrency.open_positions[i]['long']['actualised'] == True:
                if True: # TradedCurrency.is_stop_loss_activated(i, 'long', ohlc=ohlc):
                    long_position_size = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry']
                    short_position_size = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
                    TradedCurrency = processes.long_stop_loss_closing(TradedCurrency, i)
                    long = TradedCurrency.LONG[-1]
                    short = TradedCurrency.SHORT[-1]
                    logger.info('\nClosing: long stop loss closing positions')
                    logger.info("\nTradedCurrency-->open_positions[i]")
                    logger.info(f"\t[LONG] entry time: {long['entry time']}")
                    logger.info(f"\t[LONG] exit time: {long['exit time']}")
                    logger.info(f"\t[LONG] id: {long['id']}")
                    logger.info(f"\t[LONG] entry: {long['entry']}")
                    logger.info(f"\t[LONG] exit: {long['exit']}")
                    logger.info(f"\t[LONG] qty: {long['qty']}")
                    logger.info(f"\t[LONG] leverage: {long['leverage']}")
                    logger.info(f"\t[LONG] stop loss: {long['stop loss']}")
                    logger.info(f"\t[LONG] take profit: {long['take profit']}")
                    logger.info(f"\t[LONG] actualised: {long['actualised']}")
                    logger.info("\t--------------------------------------------")
                    logger.info(f"\t[SHORT] entry time: {short['entry time']}")
                    logger.info(f"\t[SHORT] exit time: {short['exit time']}")
                    logger.info(f"\t[SHORT] id: {short['id']}")
                    logger.info(f"\t[SHORT] entry: {short['entry']}")
                    logger.info(f"\t[SHORT] exit: {short['exit']}")
                    logger.info(f"\t[SHORT] qty: {short['qty']}")
                    logger.info(f"\t[SHORT] leverage: {short['leverage']}")
                    logger.info(f"\t[SHORT] stop loss: {short['stop loss']}")
                    logger.info(f"\t[SHORT] take profit: {short['take profit']}")
                    logger.info(f"\t[SHORT] actualised: {short['actualised']}")

                    logger.info("\nChecking position closed correctly")
                    long_exit_stoploss = long['exit'] == long['stop loss']
                    logger.info(f"[LONG] exit == stop loss: {long_exit_stoploss}")
                    long_pnl = round((long['exit'] / long['entry'] - 1)*100, 2)
                    logger.info(f"[LONG] pnl: {long_pnl}%")
                    logger.info(f"[LONG] non-zero exit time: {long['exit time'] != 0}")

                    logger.info(f"\nPrevious capital: {previous_capital} USDT")
                    logger.info(f"New capital: {TradedCurrency.capital} USDT")
                    logger.info(f"Long position size: {long_position_size} USDT")
                    logger.info(f"Short position size: {short_position_size} USDT")
    
    
    
    logger.info("continue_recurrent_algorithm (long stop loss closing): debug done. All variables logger.infoed")
    logger.info("Returning TradedCurrency")
    return TradedCurrency


def cra_short_stop_loss_closing(real_mode=False):
    reset_logs()
    logger.info("_________________________\nDebugging continue_recurrent_algorithm()-->short_stop_loss_closing\n_________________________")

    TradedCurrency = cra_long_stop_loss_activated(real_mode=real_mode)
    logger.info("\n_________________________________________________")
    logger.info("\n           SHORT STOP LOSS ACTIVATED              ")
    logger.info("\n_________________________________________________")
    
    previous_capital = TradedCurrency.capital


    for i in range(0, TradedCurrency.max_open_positions):        
        if TradedCurrency.open_positions[i] != None:
            # Case: closing actualised positions on long stop loss activation
            if TradedCurrency.open_positions[i]['short']['actualised'] == True:
                if True: # TradedCurrency.is_stop_loss_activated(i, 'short', ohlc=ohlc):
                    long_position_size = TradedCurrency.open_positions[i]['long']['qty'] * TradedCurrency.open_positions[i]['long']['entry']
                    short_position_size = TradedCurrency.open_positions[i]['short']['qty'] * TradedCurrency.open_positions[i]['short']['entry']
                    TradedCurrency = processes.short_stop_loss_closing(TradedCurrency, i)
                    long = TradedCurrency.LONG[-1]
                    short = TradedCurrency.SHORT[-1]
                    logger.info('\nClosing: short stop loss closing positions')
                    logger.info("\nTradedCurrency-->open_positions[i]")
                    logger.info(f"\t[LONG] entry time: {long['entry time']}")
                    logger.info(f"\t[LONG] exit time: {long['exit time']}")
                    logger.info(f"\t[LONG] id: {long['id']}")
                    logger.info(f"\t[LONG] entry: {long['entry']}")
                    logger.info(f"\t[LONG] exit: {long['exit']}")
                    logger.info(f"\t[LONG] qty: {long['qty']}")
                    logger.info(f"\t[LONG] leverage: {long['leverage']}")
                    logger.info(f"\t[LONG] stop loss: {long['stop loss']}")
                    logger.info(f"\t[LONG] take profit: {long['take profit']}")
                    logger.info(f"\t[LONG] actualised: {long['actualised']}")
                    logger.info("\t--------------------------------------------")
                    logger.info(f"\t[SHORT] entry time: {short['entry time']}")
                    logger.info(f"\t[SHORT] exit time: {short['exit time']}")
                    logger.info(f"\t[SHORT] id: {short['id']}")
                    logger.info(f"\t[SHORT] entry: {short['entry']}")
                    logger.info(f"\t[SHORT] exit: {short['exit']}")
                    logger.info(f"\t[SHORT] qty: {short['qty']}")
                    logger.info(f"\t[SHORT] leverage: {short['leverage']}")
                    logger.info(f"\t[SHORT] stop loss: {short['stop loss']}")
                    logger.info(f"\t[SHORT] take profit: {short['take profit']}")
                    logger.info(f"\t[SHORT] actualised: {short['actualised']}")

                    logger.info("\nChecking position closed correctly")
                    short_exit_stoploss = short['exit'] == short['stop loss']
                    logger.info(f"[SHORT] exit == stop loss: {short_exit_stoploss}")
                    short_pnl = round((short['entry'] / short['exit'] - 1)*100, 2)
                    logger.info(f"[SHORT] pnl: {short_pnl}%")
                    logger.info(f"[SHORT] non-zero exit time: {short['exit time'] != 0}")

                    logger.info(f"\nPrevious capital: {previous_capital} USDT")
                    logger.info(f"New capital: {TradedCurrency.capital} USDT")
                    logger.info(f"Long position size: {long_position_size} USDT")
                    logger.info(f"Short position size: {short_position_size} USDT")
    
    
    
    logger.info("continue_recurrent_algorithm (short stop loss closing): debug done. All variables logger.infoed")
    logger.info("Returning TradedCurrency")
    return TradedCurrency
        