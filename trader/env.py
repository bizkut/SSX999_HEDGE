# SSX999 Project Hedge

# Augustin BRISSART
# GitHub: @augustin999

# June 2021


import os

env_local = 'local'
env_gcp = 'gcp'


def env():
    if os.environ.get('COMPUTERNAME') == 'SSX999':
        return env_local
    return env_gcp


def is_local():
    return env() == env_local


def is_gcp():
    return env() == env_gcp


def get_var(key: str):
    return os.environ.get(key)