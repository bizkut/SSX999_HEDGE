# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import config
import processes

def main(data, context):
    # `data` and `context` are not used in this project, but are required
    # for the code to be compatible with Cloud Function

    # Case : initializing the algorithm
    if not config.TradedCurrency_path.exists():
        processes.initiate_algorithm()

    # Case : algorithm already initialized
    else:
        processes.update_trading_bot()


if __name__ == '__main__':
    main()
