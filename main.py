# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import os

from trader import config
from trader import processes
from trader import env

def main(data, context):
    # `data` and `context` are not used in this project, but are required
    # for the code to be compatible with Cloud Function

    # Case : initializing the algorithm
    if env.is_local():
        TC_path = config.TradedCurrency_path
    else:
        TC_path = config.bucket_dir / config.TradedCurrency_path
    
    if not TC_path.exists():
        if not config.measurements_path.exists():
            os.mkdir(config.measurements_path)
        processes.initiate_algorithm()

    # Case : algorithm already initialized
    else:
        processes.continue_recurrent_algorithm()
    return


if __name__ == '__main__':
    if env.is_local():
        data, context = {}, {}
        #main(data, context)
    else:
        main()
