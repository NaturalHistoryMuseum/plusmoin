import json
import jsmin

config = {}

_defaults = {
    'heartbeat': 60,
    'max_sync_delay': 120,
    'min_sync_delay': 60,
    'connect_timeout': 60,
    'is_slave_statement': 'SELECT pg_is_in_recovery()',
    'nodes': [],
    'log_level': 'error',
    'log_file': '/var/log/plusmoin/plusmoin.log',
    'pid_file': '/var/run/plusmoin/plusmoin.pid',
    'status_file': '/var/run/plusmoin/status.json',
    'user': 'nobody',
    'triggers': {},
    'trigger_timeout': 60
}

_required = ['dbname', 'user', 'password']


class ConfigRequired(Exception):
    """Exception raised when a required configuration item is missing"""
    pass


def read_config(file_name):
    """Read the given JSON configuration file and apply missing defaults

    Once read the configuration is stored in plusmoin.config.config

    @param file_name: File name to JSON configuration file
    @raises: ConfigRequired
    """
    global config
    with open(file_name) as f:
        json_config = json.loads(jsmin.jsmin(f.read()))
    for key in _defaults:
        if key not in json_config:
            json_config[key] = _defaults[key]
    for key in _required:
        if key not in json_config:
            raise ConfigRequired(key)
    for key in json_config:
        config[key] = json_config[key]