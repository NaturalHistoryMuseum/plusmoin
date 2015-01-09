from nose.tools import assert_equals, assert_items_equal
from plusmoin.lib.db import DbError
from plusmoin.pm import Plusmoin


class MockNode(object):
    def __init__(self, name, master_name, is_slave):
        self.name = name
        self.master_name = master_name
        self.is_slave = is_slave
        self.fail = False
        self.cluster_id = -1
        self.timestamp = 1000

    def refresh_role(self):
        if self.fail:
            raise DbError()

    def refresh_info(self):
        if self.fail:
            raise DbError()

    def update_heartbeat(self, timestamp):
        if self.fail:
            raise DbError()

    def to_dict(self, reset=False):
        return {
            'name': self.name,
            'master_name': self.master_name,
            'is_slave': self.is_slave,
            'cluster_id': self.cluster_id,
            'timestamp': self.timestamp
        }

class TestPlusmoin(object):
    def setUp(self):
        """Prepare some test nodes"""
        self._m1 = MockNode('a:1', None, False)
        self._m2 = MockNode('b:1', None, False)
        self._s1 = MockNode('s:1', 'a:1', True)
        self._s2 = MockNode('s:2', 'a:1', True)
        self._s3 = MockNode('s:3', 'b:1', True)
        self._s4 = MockNode('s:4', 'b:1', True)
        self._s5 = MockNode('s:5', 'c:1', True)
        self._s6 = MockNode('s:6', None, True)

    def test_startup_cluster_masters(self):
        """With no failing nodes, ensure that clusters with the correct masters
           are created at startup"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [self._m1, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )

    def test_startup_cluster_slaves(self):
        """With no failing nodes, ensure that clusters with the correct slaves
           are created at startup"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        assert_equals(len(pm.clusters), 2)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)

    def test_startup_cluster_lost(self):
        """With no failing nodes, ensure that clusters with the correct
           clusterless are created at startup"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_startup_cluster_masters_failure(self):
        """Given a failing master, ensure that clusters with the correct
           masters are created at startup"""
        self._m1.fail = True
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        assert_equals(len(pm.clusters), 1)
        assert_items_equal(
            [self._m2],
            [pm.clusters[0].master]
        )

    def test_startup_cluster_slaves_failure(self):
        """Given a failing slave, ensure that clusters with the correct slaves
           are created at startup"""
        self._s1.fail = True
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        assert_equals(len(pm.clusters), 2)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s2]
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)

    def test_startup_cluster_lost_failure(self):
        """Given a failing slave and a failing master, ensure that clusters
           with the correct clusterless are created at startup"""
        self._m1.fail = True
        self._s4.fail = True
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_items_equal(
            [self._m1, self._s1, self._s2, self._s4, self._s5, self._s6],
            pm.clusterless
        )

    def test_update(self):
        """Test an update loop with no changes and the slave nodes all getting
           the updated cluster id"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [self._m1, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_slave_out_of_sync(self):
        """Test an update loop with one slave going out of sync"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        down = l1[0]
        l1 = [l1[1]]
        down.timestamp = 500
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [(down, pm.clusters[0])],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [self._m1, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([down], pm.clusters[0].lost)
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_slave_down(self):
        """Test an update loop with one slave going down"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        down = l1[0]
        l1 = [l1[1]]
        down.fail = True
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [(down, pm.clusters[0])],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [self._m1, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([down], pm.clusters[0].lost)
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_slave_up(self):
        """Test an update loop with one slave coming back up"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        l1[0].fail = True
        pm.update_nodes()
        l1[0].fail = False
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [],
            'slave_up': [(l1[0], pm.clusters[0])]
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [self._m1, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_master_down(self):
        """Test an update loop with a master going down"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        self._m1.fail = True
        t = pm.update_nodes()
        assert_equals({
            'master_down': [(self._m1, pm.clusters[0])],
            'master_up': [],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [None, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([self._m1], pm.clusters[0].lost)
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_master_up(self):
        """Test an update loop with a master going up"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        self._m1.fail = True
        pm.update_nodes()
        up = l1[0]
        l1 = [l1[1]]
        up.is_slave = False
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [(up, pm.clusters[0])],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [up, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([self._m1], pm.clusters[0].lost)
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_master_switch(self):
        """Test an update loop with a master switch"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        self._m1.fail = True
        up = l1[0]
        l1 = [l1[1]]
        up.is_slave = False
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [(up, pm.clusters[0])],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [up, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([self._m1], pm.clusters[0].lost)
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_node_out(self):
        """Test an update loop with a slave going out (as slave)"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        out = l1[0]
        out.cluster_id = 3
        l1 = [l1[1]]
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 2)
        assert_items_equal(
            [self._m1, self._m2],
            [pm.clusters[0].master, pm.clusters[1].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_equals(0, len(pm.clusters[1].lost))
        assert_items_equal(
            [out, self._s5, self._s6],
            pm.clusterless
        )

    def test_update_node_out_new_cluster(self):
        """Test an update loop with a slave going out (as master)

        We expect a new cluster.
        """
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        out = l1[0]
        out.is_slave = False
        l1 = [l1[1]]
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 3)
        assert_items_equal(
            [self._m1, self._m2, out],
            [pm.clusters[0].master, pm.clusters[1].master,
             pm.clusters[2].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([], pm.clusters[2].slaves)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_equals(0, len(pm.clusters[1].lost))
        assert_equals(0, len(pm.clusters[2].lost))
        assert_items_equal(
            [self._s5, self._s6],
            pm.clusterless
        )

    def test_update_clusterless_master(self):
        """Test an update loop with a clusterless becoming master"""
        pm = Plusmoin([self._m1, self._m2, self._s1, self._s2, self._s3,
                       self._s4, self._s5, self._s6], 0, 0)
        if pm.clusters[0].master == self._m1:
            l1 = [self._s1, self._s2]
            l2 = [self._s3, self._s4]
        else:
            l1 = [self._s3, self._s4]
            l2 = [self._s1, self._s2]
        for node in l1:
            node.cluster_id = 0
        for node in l2:
            node.cluster_id = 1
        self._s5.is_slave = False
        t = pm.update_nodes()
        assert_equals({
            'master_down': [],
            'master_up': [],
            'slave_down': [],
            'slave_up': []
        }, t)
        assert_equals(len(pm.clusters), 3)
        assert_items_equal(
            [self._m1, self._m2, self._s5],
            [pm.clusters[0].master, pm.clusters[1].master,
             pm.clusters[2].master]
        )
        assert_items_equal(l1, pm.clusters[0].slaves)
        assert_items_equal(l2, pm.clusters[1].slaves)
        assert_items_equal([], pm.clusters[2].slaves)
        assert_equals(0, len(pm.clusters[0].lost))
        assert_equals(0, len(pm.clusters[1].lost))
        assert_equals(0, len(pm.clusters[2].lost))
        assert_items_equal(
            [self._s6],
            pm.clusterless
        )