#!/usr/bin/env python
""" plusmoin

plusmoin is a daemon to help manage clusters of PostgreSQL servers setup in
master/slave replication.

Usage: plusmoin [options] (start|stop|reload|status)

Options:
    -h --help       Show this screen.
    --version       Show version.
    -c CONFIG-FILE  Configuration file [default: /etc/plusmoin/plusmoin.json]
    -x              Do not daemonize, and output logs to stdout. Useful for
                    testing.
"""
import os
import sys
import pwd
import signal
import time
import logging
import traceback

import docopt
import daemon
from daemon.pidfile import TimeoutPIDLockFile

from plusmoin.pm import run as run_service
from plusmoin.config import read_config, ConfigRequired, config

VERSION = '0.1'


def run_start(logger, no_daemon):
    """ Start plusmoin

    Args:
        logger (Logger): A Logger object
        no_daemon (bool): True to disable forking into a daemon
    """
    if no_daemon:
        run_service()
    else:
        with daemon.DaemonContext(
            pidfile=TimeoutPIDLockFile(config['pid_file']),
            uid=pwd.getpwnam(config['daemon_user']).pw_uid
        ):
            try:
                run_service()
            except Exception:
                # There is no one above us, so we catch and log all exceptions.
                logger.error(traceback.format_exc())


def run_stop(logger):
    """ Stop plusmoin """
    # Look for pid file
    if not os.path.exists(config['pid_file']):
        sys.stderr.write(
            'PID file {} not found - is the daemon running?'.format(
                config['pid_file']
            )
        )
        sys.exit(1)

    # Read pid
    with open(config['pid_file']) as f:
        try:
            pid = int(f.read())
        except IOError, ValueError:
            sys.stderr.write("Could not read pid in {}".format(
                config['pid_file']
            ))
            sys.exit(1)

    # Check the process exists
    try:
        os.kill(pid, 0)
    except OSError:
        sys.stderr.write(
            'PID file {} found, but no matching process'.format(
                config['pid_file']
            )
        )
        sys.exit(1)

    # SIGTERM and wait.
    try:
        print "Sending SIGTERM to {}...".format(pid)
        os.kill(pid, signal.SIGTERM)
    except OSError:
        sys.stderr.write(
            'Error attempting to stop process {}'.format(pid)
        )
        sys.exit(1)
    start = time.time()
    done = False
    while not done and time.time() - start < 3.0:
        try:
            os.kill(pid, 0)
        except OSError:
            done = True
    if not done:
        print "Process did not stop. Sending SIGKILL"
        os.kill(pid, signal.SIGKILL)
    else:
        print "Done!"
    sys.exit(0)


def run_reload(logger):
    """ Reload plusmoin """
    sys.stderr.write("Not implemented\n")
    exit(1)


def run_status(logger):
    """ Output plusmoin status object """
    with open(config['status_file']) as f:
        sys.stdout.write(f.read() + "\n")
    sys.exit(0)


def run(argv):
    """Setup tools entry point"""
    # Read arguments
    arguments = docopt.docopt(__doc__, argv=argv, help=True, version=VERSION)
    config_file = arguments['-c']
    no_daemon = arguments['-x']
    command = 'status'
    for available_command in ['start', 'stop', 'status', 'reload']:
        if arguments[available_command]:
            command = available_command

    # Read config
    try:
        read_config(config_file)
    except IOError:
        sys.stderr.write('Could not find config file {}'.format(config_file))
        sys.exit(1)
    except ConfigRequired as e:
        sys.stderr.write('Missing required configuration: {}'.format(str(e)))
        sys.exit(1)

    # Setup logger
    level_map = {
        'error': logging.ERROR,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    logger = logging.getLogger()
    try:
        logger.setLevel(level_map[config['log_level']])
    except KeyError:
        sys.stderr.write('Unknown log level {}'.format(config['log_level']))
        sys.exit(1)
    if no_daemon:
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(config['log_file'])
    logger.addHandler(handler)

    # Dispatch
    if command == 'start':
        run_start(logger, no_daemon)

if __name__ == '__main__':
    run(sys.argv)