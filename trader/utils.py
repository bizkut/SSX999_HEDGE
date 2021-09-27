# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import pickle
from typing import Union

import pandas as pd
from google.cloud import storage
from pathy.base import Pathy
from pathlib import Path

try:
    from trader import config
    from trader import env
except:
    import config
    import env


def get_blob(path: Union[Path, Pathy]):
    storage_client = storage.Client()
    bucket = storage_client.bucket(config.bucket_dir.name)
    return bucket.blob(path)


def dump_as_pickle(content, path: Union[Path, Pathy]):
    if env.is_local():
        with open(path, 'wb') as _file:
            pickle.dump(content, _file)
    else:
        blob = get_blob(path=str(path))
        pickle_out = pickle.dumps(content)
        blob.upload_from_string(pickle_out)
    return


def load_pickle(path: Union[Path, Pathy]):
    if env.is_local():
        with open(str(path), 'rb') as _file:
            return pickle.load(_file)
    blob = get_blob(path=str(path))
    pickle_in = blob.download_as_string()
    return pickle.loads(pickle_in)


def dump_as_csv(content: pd.DataFrame, path: Union[Path, Pathy]):
    # Pandas can write directly in a Bucket
    content.to_csv(str(path), sep=config.CSV_SEP, encoding='utf-8')
    return


def read_csv(path: Union[Path, Pathy]):
    df = pd.read_csv(str(path), sep=config.CSV_SEP, encoding='utf-8')
    if df.columns[0] == 'Unnamed: 0':
        df = df[df.columns[1:]]
    return df


def read_file(path: Union[Path, Pathy]):
    if env.is_local():
        with open(path, 'r') as _file:
            return _file.read().strip()
    blob = get_blob(path=str(path))
    _file = blob.download_as_string()
    return _file.strip()
