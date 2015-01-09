from nose.tools import assert_equals, assert_raises, assert_true, assert_false
from nose.tools import assert_items_equal
from mock import Mock
from plusmoin.config import config
from plusmoin.lib.cluster import Cluster
from plusmoin.lib.db import DbError

# Test case:
# master gone
# slave should not move to lost!

class TestCluster(object):
    def setUp(self):
        """Prepare a cluster with a mocked master"""
        mock_master = Mock()
        mock_master.is_slave = False
        mock_master.name = 'a:1'
        mock_master.cluster_id = 0
        mock_master.timestamp = 1000
        self._cluster = Cluster(
            cluster_id=0,
            max_sync_delay=10,
            recover_sync_delay=5,
            master=mock_master
        )

    def test_to_dict(self):
        """ Ensure to_dict returns the expected information """
        mock_slave = Mock(
            is_slave=True,
            master_name='a:1',
            cluster_id=0,
            timestamp=1000
        )
        mock_lost = Mock(
            is_slave=True,
            master_name='a:1',
            cluster_id=0,
            timestamp=700
        )
        self._cluster.add_node(mock_slave)
        self._cluster.add_node(mock_lost)
        d = self._cluster.to_dict(reset=True)
        assert_items_equal(d.keys(), [
            'cluster_id', 'has_master', 'master', 'slaves', 'lost'
        ])
        assert_equals(0, d['cluster_id'])
        assert_true(d['has_master'])
        assert_equals(self._cluster.master.to_dict(), d['master'])
        assert_equals(1, len(d['slaves']))
        assert_equals(mock_slave.to_dict(), d['slaves'][0])
        assert_equals(1, len(d['lost']))
        assert_equals(mock_lost.to_dict(), d['lost'][0])


    def test_has_master_property(self):
        """Test the has_master property is updated"""
        assert_true(self._cluster.has_master)
        self._cluster.master = None
        assert_false(self._cluster.has_master)

    def test_add_up_to_date_slave_node(self):
        """Test we can add up to date slave nodes to a cluster"""
        mock_slave = Mock()
        mock_slave.is_slave = True
        mock_slave.master_name = 'a:1'
        mock_slave.cluster_id = 0
        mock_slave.timestamp = 1000
        self._cluster.add_node(mock_slave)
        assert_items_equal(self._cluster.slaves, [mock_slave])
        assert_items_equal(self._cluster.lost, [])

    def test_add_out_of_sync_slave_node(self):
        """Ensure adding an out-of-sync slave goes to lost nodes"""
        mock_slave = Mock()
        mock_slave.is_slave = True
        mock_slave.master_name = 'a:1'
        mock_slave.cluster_id = 0
        mock_slave.timestamp = 700
        self._cluster.add_node(mock_slave)
        assert_items_equal(self._cluster.slaves, [])
        assert_items_equal(self._cluster.lost, [mock_slave])

    def test_add_slave_node_with_wrong_master(self):
        """Ensure adding synced slave with wrong master goes to lost nodes"""
        mock_slave = Mock()
        mock_slave.is_slave = True
        mock_slave.master_name = 'b:1'
        mock_slave.cluster_id = 0
        mock_slave.timestamp = 1000
        self._cluster.add_node(mock_slave)
        assert_items_equal(self._cluster.slaves, [])
        assert_items_equal(self._cluster.lost, [mock_slave])

    def test_add_second_master_raises(self):
        """Ensure adding a second master raises an exception"""
        mock_slave = Mock()
        mock_slave.is_slave = False
        mock_slave.master_name = 'a:1'
        mock_slave.cluster_id = 1
        mock_slave.timestamp = 1000
        assert_raises(ValueError, self._cluster.add_node, mock_slave)


class TestUpdateCluster(object):
    """Test cases specifically for Cluster.update_cluster"""
    def setUp(self):
        """Prepare a cluster with a mocked master, slave and lost nodes"""
        self._master = Mock(
            is_slave=False,
            name='a:1',
            cluster_id=0,
            timestamp=1000
        )
        self._slave_1 = Mock(
            is_slave=True,
            master_name='a:1',
            cluster_id=0,
            timestamp=1000
        )
        self._slave_2 = Mock(
            is_slave=True,
            master_name='a:1',
            cluster_id=0,
            timestamp=1000
        )
        self._lost_1 = Mock(
            is_slave=True,
            master_name='a:1',
            cluster_id=0,
            timestamp=1000
        )
        self._lost_1.refresh_role.side_effect = DbError
        self._lost_2 = Mock(
            is_slave=True,
            master_name='a:1',
            cluster_id=0,
            timestamp=1000
        )
        self._lost_2.refresh_role.side_effect = DbError
        self._cluster = Cluster(
            cluster_id=0,
            max_sync_delay=10,
            recover_sync_delay=5,
            master=self._master
        )
        self._cluster.slaves = [self._slave_1, self._slave_2]
        self._cluster.lost = [self._lost_1, self._lost_2]

    def test_no_change(self):
        """Test a cluster update with no node status change"""
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_master_down(self):
        """Test a cluster update with a master going down"""
        self._master.refresh_role.side_effect = DbError
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': self._master,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2, self._master],
                           self._cluster.lost)
        assert_equals(None, self._cluster.master)

    def test_master_becomes_slave(self):
        """Test a cluster update with a master downgrading to slave"""
        self._master.is_slave = True
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': self._master,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2, self._master],
                           self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(None, self._cluster.master)

    def test_slave_master_up(self):
        """Test a cluster update with a master going up from the slaves"""
        self._cluster.master = None
        self._slave_1.is_slave = False
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': self._slave_1,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(self._slave_1, self._cluster.master)

    def test_slave_master_up_cluster_id(self):
        """Check that when a slave becomes a master, it's cluster id is forced
           to that of the cluster"""
        self._cluster.master = None
        self._slave_1.is_slave = False
        self._slave_1.cluster_id = 1
        self._cluster.update_cluster()
        assert_equals(self._slave_1.cluster_id, 0)

    def test_lost_master_up(self):
        """Test a cluster update with a master going up from the lost nodes"""
        self._cluster.master = None
        self._lost_1.is_slave = False
        self._lost_1.refresh_role = Mock()
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': self._lost_1,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_2], self._cluster.lost)
        assert_equals(self._lost_1, self._cluster.master)

    def test_lost_master_up_cluster_id(self):
        """Check that when a lost becomes a master, it's cluster id is forced
           to that of the cluster"""
        self._cluster.master = None
        self._lost_1.is_slave = False
        self._lost_1.refresh_role = Mock()
        self._lost_1.cluster_id = 1
        self._cluster.update_cluster()
        assert_equals(self._lost_1.cluster_id, 0)

    def test_slave_failed_master_up(self):
        """Test a cluster update with a slave that becomes master, but fails
           to update the heartbeat"""
        self._cluster.master = None
        self._slave_1.is_slave = False
        self._slave_1.update_heartbeat.side_effect = DbError
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [self._slave_1],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2, self._slave_1],
                      self._cluster.lost)
        assert_equals(None, self._cluster.master)

    def test_lost_failed_master_up(self):
        """Test a cluster update with a lost that becomes master, but fails to
           update the heartbeat"""
        self._cluster.master = None
        self._lost_1.is_slave = False
        self._lost_1.refresh_role = Mock()
        self._lost_1.update_heartbeat.side_effect = DbError
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(None, self._cluster.master)

    def test_master_down_slave_master_up(self):
        """Test a cluster update with a master going down and master going up
           from the slaves"""
        self._master.refresh_role.side_effect = DbError
        self._slave_1.is_slave = False
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': self._slave_1,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2, self._master],
                      self._cluster.lost)
        assert_equals(self._slave_1, self._cluster.master)
        assert_true(self._cluster.has_master)

    def test_master_down_lost_master_up(self):
        """Test a cluster update with a master going down and master going up
           from the lost"""
        self._master.refresh_role.side_effect = DbError
        self._lost_1.is_slave = False
        self._lost_1.refresh_role = Mock()
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': self._lost_1,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_2, self._master], self._cluster.lost)
        assert_equals(self._lost_1, self._cluster.master)
        assert_true(self._cluster.has_master)

    def test_slave_down(self):
        """Test a cluster with a slave going down"""
        self._slave_1.refresh_role.side_effect = DbError
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [self._slave_1],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2, self._slave_1],
                      self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_slave_out_of_sync(self):
        """Test a cluster with a slave going out of sync"""
        self._slave_1.timestamp = 900
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [self._slave_1],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2, self._slave_1],
                      self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_lost_node_back_but_out_of_sync(self):
        """Test a cluster update where a lost node comes back but is out
           of sync"""
        self._lost_1.refresh_role = Mock()
        self._lost_1.timestamp = 900
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_second_master_from_slave_out(self):
        """ Check that if a slave becomes a master when we already have one,
            it is sent out."""
        self._slave_1.is_slave = False
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': [self._slave_1]
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_second_master_from_lost_out(self):
        """ Check that if a lost comes back as a master when we already have
            one, it is sent out."""
        self._lost_1.is_slave = False
        self._lost_1.refresh_role = Mock()
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': [self._lost_1]
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_master_down_two_slaves_master_up(self):
        """Test a cluster update with a master going down two slaves coming
           back as master at the same time"""
        self._master.refresh_role.side_effect = DbError
        self._slave_1.is_slave = False
        self._slave_2.is_slave = False
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': self._slave_1,
            'slaves_down': [],
            'slaves_up': [],
            'out': [self._slave_2]
        })
        assert_items_equal([], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2, self._master],
                           self._cluster.lost)
        assert_equals(self._slave_1, self._cluster.master)
        assert_true(self._cluster.has_master)

    def test_master_down_slave_and_lost_master_up(self):
        """Test a cluster update with a master going down and a slave and lost
           coming back as master at the same time"""
        self._master.refresh_role.side_effect = DbError
        self._slave_1.is_slave = False
        self._lost_1.refresh_role = Mock()
        self._lost_1.is_slave = False
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': self._slave_1,
            'slaves_down': [],
            'slaves_up': [],
            'out': [self._lost_1]
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_2, self._master],
                           self._cluster.lost)
        assert_equals(self._slave_1, self._cluster.master)
        assert_true(self._cluster.has_master)

    def test_slave_in_sync_with_different_cluster_id(self):
        """Check that a slave that is in-sync but has a wrong cluster id is
           moved out"""
        self._slave_1.cluster_id = 1
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': [self._slave_1]
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_slave_out_of_sync_with_different_cluster_id(self):
        """Check that a slave that is out of sync and has a wrong cluster id is
           NOT moved out"""
        self._slave_1.cluster_id = 1
        self._slave_1.timestamp = 500
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [self._slave_1],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_2], self._cluster.slaves)
        assert_items_equal([self._slave_1, self._lost_1, self._lost_2],
                           self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_lost_with_different_cluster_id(self):
        """Check that a lost node which has a wrong cluster id is NOT
           moved out"""
        self._lost_1.cluster_id = 1
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        })
        assert_items_equal([self._slave_1, self._slave_2], self._cluster.slaves)
        assert_items_equal([self._lost_1, self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)

    def test_lost_back_with_different_cluster_id(self):
        """Check that a lost node that comes back in sync but with a wrong
           cluster id is moved out, and nothing is triggered"""
        self._lost_1.refresh_role = Mock()
        self._lost_1.cluster_id = 1
        status = self._cluster.update_cluster()
        assert_equals(status, {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': [self._lost_1]
        })
        assert_items_equal([self._slave_1, self._slave_2],
                           self._cluster.slaves)
        assert_items_equal([self._lost_2], self._cluster.lost)
        assert_equals(self._master, self._cluster.master)
