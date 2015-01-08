import logging
import shlex

from subprocess32 import Popen, PIPE, STDOUT, TimeoutExpired

from plusmoin.config import config


def trigger(name, data):
    """Runs the named trigger with given active node and cluster

    Args:
        name (str): Name of the trigger
        data (str): Data to send to the trigger
    """
    logger = logging.getLogger()
    if name not in config['triggers'] or config['triggers'][name] is None:
        return
    command = shlex.split(config['triggers'][name])
    try:
        proc = Popen(command, stdout=PIPE, stdin=PIPE, stderr=STDOUT)
    except OSError as e:
        logger.error(
            "Could not execute trigger {} with script {}: {}".format(
                name, config['triggers'][name], str(e)
            ))
        return
    try:
        (output, _) = proc.communicate(data, timeout=config['trigger_timeout'])
    except TimeoutExpired:
        proc.kill()
        proc.communicate(data)
        logger.error("Trigger {} with script {} timed out".format(
            name, config['triggers'][name]
        ))
        return
    if proc.returncode != 0:
        logger.error(
            ("Trigger {} with script {} exited with status code {}." +
             "Output: {}").format(name, config['triggers'][name],
                                  proc.returncode, output)
        )
