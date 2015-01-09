import os
import sys
import tempfile
import logging
import shutil
import json
from multiprocessing import Process
from containers import DockerContainers
from plusmoin.cli import run as run_cli


def plusmoin(*argv):
    """ Run the plusmoin cli with the given argv

    Args:
        argv (list): Argv
    """
    run_cli(argv)


class BaseTest(object):
    """ Class to be inherited by all test classes """
    def setUp(self):
        """ Setup """
        self.root = tempfile.mkdtemp()
        self.pm = None
        self.containers = None
        logger = logging.getLogger('containers')
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)

    def teardown(self):
        """ Clean up temporary directory """
        if self.pm is not None:
            self.pm.terminate()
        if self.containers is not None:
            self.containers.stop()
            self.containers.remove()
        shutil.rmtree(self.root)

    def start_containers(self, containers):
        """ Start the listed containers """
        self.containers = DockerContainers(
            os.path.dirname(__file__),
            containers
        )
        self.containers.build()
        self.containers.start()

    def start_plusmoin(self, config):
        """ Start the plusmoin daemon

        Args:
            config (dict): Configuration
        """
        with open(os.path.join(self.root, 'config.json'), 'w') as f:
            f.write(json.dumps(config))
        self.pm = Process(target=plusmoin, args=(
            '-x', '-c', os.path.join(self.root, 'config.json'), 'start'
        ))
        self.pm.start()

    def trigger_command(self, name):
        """ Return the trigger command for the given trigger

        Args:
            name (str): Name of the trigger
        """
        cmd = os.path.join(os.path.dirname(__file__), 'trigger.py')
        return '{cmd} {trg_name} {trg_file}'.format(
            cmd=cmd,
            trg_name=name,
            trg_file=os.path.join(self.root, 'triggers.json')
        )

    def get_triggers(self, clean=False):
        """ Return a json object showing the list of triggers run

        Args:
            clean (bool, optional): If True, empty the trigger file

        Returns:
            dict: Dictionary with a key for each trigger that was run
                  associated to the data it was run with
        """
        file_name = os.path.join(self.root, 'triggers.json')
        if not os.path.exists(file_name):
            return {}
        with open(file_name) as f:
            data = json.loads(f.read())
        if clean:
            with open(file_name, 'w') as f:
                f.write(json.dumps({}))
        return data
