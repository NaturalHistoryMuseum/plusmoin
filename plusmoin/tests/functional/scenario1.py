import os
import json
import time
from base import BaseTest
from nose.tools import assert_equals, assert_true, assert_items_equal
from nose.tools import assert_false


class TestScenario1(BaseTest):
    def test_scenario_1(self):
        """ Run all the steps in the test scenario """
        self.start_containers_and_plusmoin()
        self.check_the_status_file()
        self.check_the_triggers()
        self.bring_slave_down()
        self.check_status_with_missing_slave()
        self.check_triggers_after_slave_went_down()
        self.bring_slave_back()
        self.check_the_status_file()
        self.check_triggers_after_slave_came_back()
        self.bring_master_down()
        self.check_status_with_missing_master()
        self.check_triggers_after_master_went_down()
        self.bring_master_back()
        self.check_the_status_file()
        self.check_triggers_after_master_came_back()

    def start_containers_and_plusmoin(self):
        """ Start the containers and plusmoin """
        self.start_containers([
            {
                'image': 'pm_test_master',
                'name': 'pg_master_1',
                'ports': {
                    5432: 15432
                },
                'links': {}
            },
            {
                'image': 'pm_test_slave',
                'name': 'pg_slave_1',
                'ports': {
                    5432: 25432
                },
                'links': {
                    'pg_master_1': 'pg_master'
                }
            },
            {
                'image': 'pm_test_slave',
                'name': 'pg_slave_2',
                'ports': {
                    5432: 35432
                },
                'links': {
                    'pg_master_1': 'pg_master'
                }
            }
        ])
        time.sleep(10)
        self.start_plusmoin({
            'dbname': 'plusmoin',
            'user': 'plusmoin',
            'password': 'secret',
            'heartbeat': 1,
            'max_sync_delay': 5,
            'recover_sync_delay': 2,
            'nodes': [{
                'host': 'localhost',
                'port': 15432
            }, {
                'host': 'localhost',
                'port': 25432
            }, {
                'host': 'localhost',
                'port': 35432
            }],
            'triggers': {
                'plusmoin_up': self.trigger_command('plusmoin_up'),
                'plusmoin_heartbeat': self.trigger_command('plusmoin_heartbeat'),
                'master_up': self.trigger_command('master_up'),
                'master_down': self.trigger_command('master_down'),
                'slave_up': self.trigger_command('slave_up'),
                'slave_down': self.trigger_command('slave_down')
            },
            'trigger_timeout': 1,
            'log_file': os.path.join(self.root, 'pm.log'),
            'log_level': 'debug',
            'daemon_user': 'nobody',
            'pid_file': os.path.join(self.root, 'pm.pid'),
            'status_file': os.path.join(self.root, 'status.json'),
            'connect_timeout': 1,
            'is_slave_statement': 'SELECT pg_is_in_recovery()'
        })
        time.sleep(10)

    def check_the_status_file(self):
        """ Test the status file """
        with open(os.path.join(self.root, 'status.json')) as f:
            data = json.loads(f.read())
            assert_equals(len(data['clusters']), 1)
            assert_equals(len(data['clusterless']), 0)
            c = data['clusters'][0]
            assert_equals(c['cluster_id'], 0)
            assert_true(c['has_master'])
            assert_equals(c['master'], {
                'is_slave': False,
                'master_name': '',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 15432
            })
            assert_equals(len(c['slaves']), 2)
            assert_items_equal(c['slaves'], [{
                'is_slave': True,
                'master_name': 'localhost:15432',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 25432
            }, {
                'is_slave': True,
                'master_name': 'localhost:15432',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 35432
            }])
            assert_equals(0, len(c['lost']))

    def check_the_triggers(self):
        """ Test the triggers """
        triggers = self.get_triggers(clean=True)
        assert_items_equal(triggers.keys(), [
            'plusmoin_up',
            'plusmoin_heartbeat'
        ])

    def bring_slave_down(self):
        """ Take the slave down """
        self.containers.stop_container('pg_slave_1')
        time.sleep(10)

    def check_status_with_missing_slave(self):
        """ Test the status file """
        with open(os.path.join(self.root, 'status.json')) as f:
            data = json.loads(f.read())
            assert_equals(len(data['clusters']), 1)
            assert_equals(len(data['clusterless']), 0)
            c = data['clusters'][0]
            assert_equals(c['cluster_id'], 0)
            assert_true(c['has_master'])
            assert_equals(c['master'], {
                'is_slave': False,
                'master_name': '',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 15432
            })
            assert_equals(len(c['slaves']), 1)
            assert_equals(c['slaves'][0], {
                'is_slave': True,
                'master_name': 'localhost:15432',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 35432
            })
            assert_equals(len(c['lost']), 1)
            assert_equals(c['lost'][0], {
                'is_slave': True,
                'master_name': 'localhost:15432',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 25432
            })

    def check_triggers_after_slave_went_down(self):
        triggers = self.get_triggers(clean=True)
        assert_items_equal(triggers.keys(), [
            'plusmoin_heartbeat',
            'slave_down'
        ])
        assert_equals(triggers['slave_down']['trigger'], {
            'is_slave': True,
            'master_name': 'localhost:15432',
            'cluster_id': 0,
            'host': 'localhost',
            'port': 25432
        })

    def bring_slave_back(self):
        """ Bring the slave back """
        self.containers.start_container('pg_slave_1')
        time.sleep(10)

    def check_triggers_after_slave_came_back(self):
        triggers = self.get_triggers(clean=True)
        assert_items_equal(triggers.keys(), [
            'plusmoin_heartbeat',
            'slave_up'
        ])
        assert_equals(triggers['slave_up']['trigger'], {
            'is_slave': True,
            'master_name': 'localhost:15432',
            'cluster_id': 0,
            'host': 'localhost',
            'port': 25432
        })

    def bring_master_down(self):
        """ Bring the master down """
        self.containers.pause_container('pg_master_1')
        time.sleep(10)

    def check_status_with_missing_master(self):
        """ Test the status file """
        with open(os.path.join(self.root, 'status.json')) as f:
            data = json.loads(f.read())
            assert_equals(len(data['clusters']), 1)
            assert_equals(len(data['clusterless']), 0)
            c = data['clusters'][0]
            assert_equals(c['cluster_id'], 0)
            assert_false(c['has_master'])
            assert_equals(c['master'], None)
            assert_equals(len(c['slaves']), 2)
            assert_equals(len(c['lost']), 1)
            assert_equals(c['lost'][0], {
                'is_slave': False,
                'master_name': '',
                'cluster_id': 0,
                'host': 'localhost',
                'port': 15432
            })

    def check_triggers_after_master_went_down(self):
        triggers = self.get_triggers(clean=True)
        assert_items_equal(triggers.keys(), [
            'plusmoin_heartbeat',
            'master_down'
        ])
        assert_equals(triggers['master_down']['trigger'], {
            'is_slave': False,
            'master_name': '',
            'cluster_id': 0,
            'host': 'localhost',
            'port': 15432
        })

    def bring_master_back(self):
        self.containers.unpause_container('pg_master_1')
        time.sleep(10)

    def check_triggers_after_master_came_back(self):
        triggers = self.get_triggers(clean=True)
        assert_items_equal(triggers.keys(), [
            'plusmoin_heartbeat',
            'master_up'
        ])
        assert_equals(triggers['master_up']['trigger'], {
            'is_slave': False,
            'master_name': '',
            'cluster_id': 0,
            'host': 'localhost',
            'port': 15432
        })





if __name__ == '__main__':
    t = TestScenario1()
    try:
        t.setUp()
        t.test_scenario_1()
    finally:
        t.teardown()
