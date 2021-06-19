# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import pickle
from typing import Union

import numpy as np
import pandas as pd
from google.cloud import storage
from pandas import Timestamp as ts
from pathy.base import Pathy
from pathlib import Path

import config, env


def get_blob(path: Union[Path, Pathy]):
    storage_client = storage.Client()
    bucket = storage_client.bucket(config.bucket_dir.name)
    return bucket.blob(path)


def dump_as_pickle(content, path: Union[Path, Pathy]):
    if env.is_local():
        with open(path, 'wb') as _file:
            pickle.dump(content, _file)
    else:
        blob = get_blob(path=f'{config.generated_data_dir.name}/{path.name}')
        pickle_out = pickle.dumps(content)
        blob.upload_from_string(pickle_out)


def load_pickle(path: Union[Path, Pathy]):
    if env.is_local():
        with open(path, 'rb') as _file:
            return pickle.load(_file)
    blob = get_blob(path=f'{config.generated_data_dir.name}/{path.name}')
    pickle_in = blob.download_as_string()
    return pickle.loads(pickle_in)


def read_file(path: Union[Path, Pathy]):
    if env.is_local():
        with open(path, 'r') as _file:
            return _file.read().strip()
    blob = get_blob(path=f'{config.keys_dir.name}/{path.name}')
    _file = blob.download_as_string()
    return _file.strip()


def dump_as_csv(content: pd.DataFrame, path: Union[Path, Pathy]):
    # Pandas can write directly in a Bucket
    content.to_csv(path, sep=config.CSV_SEP, encoding='utf-8')


def read_csv(path: Union[Path, Pathy]):
    if env.is_local():
        df = pd.read_csv(path, sep=config.CSV_SEP, encoding='utf-8')
        if df.columns[0] == 'Unnamed: 0':
            df = df[df.columns[1:]]
        return df
    # Write GCP side or verify if pandas can read directly in a Bucket
    return


def StoUnix(tsSeries):
    """
    Convert a series of multiple string-like timestamp into a unix timestamp.
    """
    return tsSeries.astype(np.int64)//10**9


def StoTs(unixSeries):
    """
    Convert a series of multiple unix timestamp into a string-like timestamp.
    """
    return pd.to_datetime(unixSeries, utc=True, unit='s')


def toTs(unixDate):
    """
    Convert a single unixTimestamp to UTC time.
    """
    return ts(unixDate, tz='utc', unit='s')


def toUnix(tsDate):
    """
    Convert a single UTC Time to UnixTimestamp.
    """
    return StoUnix(pd.Series([tsDate]))[0]

def set_pair(base):
        """
        Return a correct pair with any base and quote, 
        taking into consideration currencies' specificities.
        """
        pair = 'X' + base.upper() + 'Z' + config.QUOTE.upper()
        if base.upper() in config.SPECIAL_BASES:
            pair = base.upper() + config.QUOTE.upper()
        return pair
