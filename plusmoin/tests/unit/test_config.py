import os
import json
import shutil
import tempfile

from nose.tools import assert_raises, assert_true, assert_in, assert_equals
from plusmoin.config import read_config, config, ConfigRequired


class TestConfig(object):
    def setUp(self):
        """Create a temporary folder to store config files"""
        self._temp = tempfile.mkdtemp()

    def tearDown(self):
        """Remove temporary folder"""
        shutil.rmtree(self._temp)

    def test_config_object_populated(self):
        """Tests the config.config object is populated as expected"""
        tcfg = {
            'user': '1',
            'password': '2',
            'dbname': '3',
            'heartbeat': 1000,
            'sync_delay': 99
        }
        conf = os.path.join(self._temp, "test_raises_if_required_missing.conf")
        with open(conf, 'w') as f:
            f.write(json.dumps(tcfg))
        read_config(conf)
        print config
        for key in tcfg:
            assert_in(key, config)
            assert_equals(tcfg[key], config[key])

    def test_raises_if_required_missing(self):
        """Tests an exception is raised if a required field is missing"""
        conf = os.path.join(self._temp, "test_raises_if_required_missing.conf")
        with open(conf, 'w') as f:
            f.write(json.dumps({
            }))
        assert_raises(ConfigRequired, read_config, conf)

    def test_defaults_are_set(self):
        """Tests that default values are set for non-required fields"""
        conf = os.path.join(self._temp, "test_defaults_are_set.conf")
        with open(conf, 'w') as f:
            f.write(json.dumps({
                'user': '1',
                'dbname': '2',
                'password': '3'
            }))
        read_config(conf)
        assert_true(len(config) > 3)
