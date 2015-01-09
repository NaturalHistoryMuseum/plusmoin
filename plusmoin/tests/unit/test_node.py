from nose.tools import assert_equals, assert_not_equals, assert_true
from nose.tools import assert_false
from mock import patch, call
from plusmoin.lib.node import Node


class MockConnection(object):
    def __enter__(self):
        return 'connection'

    def __exit__(self, tp, value, tb):
        pass


class TestNode(object):
    def test_name(self):
        """Ensure the node gets a unique name build from host and port"""
        n1 = Node('a', 1)
        n2 = Node('a', 2)
        n3 = Node('b', 1)
        n4 = Node('a', 1)
        assert_not_equals(n1.name, n2.name)
        assert_not_equals(n1.name, n3.name)
        assert_equals(n1.name, n4.name)

    @patch('plusmoin.lib.node.db')
    def test_refresh_role(self, mock_db):
        """Ensure refresh role is updated as per the database API"""
        mock_db.get_connection.return_value = MockConnection()
        mock_db.is_slave.return_value = True
        node = Node('a', 1)
        node.refresh_role()
        assert_true(node.is_slave)
        mock_db.is_slave.return_value = False
        node.refresh_role()
        assert_false(node.is_slave)

    @patch('plusmoin.lib.node.db')
    def test_get_info(self, mock_db):
        """Ensure get info is updated as per the database API"""
        mock_db.get_connection.return_value = MockConnection()
        mock_db.get_info.return_value = (12, 'hello:99', 12345)
        node = Node('a', 1)
        node.refresh_info()
        assert_equals(12, node.cluster_id)
        assert_equals('hello:99', node.master_name)
        assert_equals(12345, node.timestamp)

    @patch('plusmoin.lib.node.db')
    def test_to_dict(self, mock_db):
        """ Test to_dict """
        mock_db.get_connection.return_value = MockConnection()
        mock_db.is_slave.return_value = True
        mock_db.get_info.return_value = (12, 'hello:99', 12345)
        node = Node('a', 1)
        node.refresh_role()
        node.refresh_info()
        assert_equals(node.to_dict(), {
            'host': 'a',
            'port': 1,
            'master_name': 'hello:99',
            'cluster_id': 12,
            'is_slave': True
        })

    @patch('plusmoin.lib.node.db')
    def test_update_heartbeat(self, mock_db):
        """Ensure update heartbeat invokes the database API """
        mock_db.get_connection.return_value = MockConnection()
        mock_db.create_heartbeat_table.return_value = True
        mock_db.update_heartbeat_table.return_value = True
        node = Node('a', 1)
        node.cluster_id = 33
        node.update_heartbeat(12345)
        assert_true(mock_db.create_heartbeat_table.called)
        assert_true(mock_db.update_heartbeat_table.called)
        assert_equals(
            call(33, 'a:1', 12345, 'connection'),
            mock_db.update_heartbeat_table.call_args
        )

    @patch('plusmoin.lib.node.db')
    def test_update_heartbeat_timestamp(self, mock_db):
        """Ensure calling update heartbeat updates the node's timestamp"""
        mock_db.get_connection.return_value = MockConnection()
        mock_db.create_heartbeat_table.return_value = True
        mock_db.update_heartbeat_table.return_value = True
        node = Node('a', 1)
        node.cluster_id = 33
        node.update_heartbeat(12345)
        assert_equals(node.timestamp, 12345)
