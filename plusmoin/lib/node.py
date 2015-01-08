from plusmoin.lib import db


class Node(object):
    """Represents a postgresql server

    Args:
        host (str): Host name of the server
        port (int): Port of the server

    Attributes:
        host (str): Host name of the server
        port (int): Port of the server
        name (str): Internal name of the server, build from host name and port
        is_slave (bool): True if this is a slave node
        cluster_id (int): Cluster id of the node, as fetched from the database
        master_name (str): Name of the server, as fetched from the database
        timestamp (int): Timestamp of the last seen beat, as fetched from the
            database
    """
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.name = "{}:{}".format(host, port)
        self.is_slave = False
        self.cluster_id = -1
        self.master_name = ''
        self.timestamp = 0
        self._dict = None

    def refresh_role(self):
        """Call the database to refresh the role of this node

        Raises:
            plusmoin.lib.db.DbError: For any error while fetching the role
        """
        with db.get_connection(self.host, self.port) as connection:
            self.is_slave = db.is_slave(connection)

    def refresh_info(self):
        """Refresh the node's information from the database

        Raises:
            plusmoin.lib.db.DbError: On any database error
        """
        with db.get_connection(self.host, self.port) as connection:
            (cluster_id, master_name, timestamp) = db.get_info(connection)
            self.cluster_id = cluster_id
            self.master_name = master_name
            self.timestamp = timestamp

    def update_heartbeat(self, timestamp):
        """Update the node's heartbeat (only on master nodes)

        Args:
            timestamp (int): The timestamp to set for heartbeat

        Raises:
            plusmoin.lib.db.DbError: On any database error
        """
        with db.get_connection(self.host, self.port) as connection:
            db.create_heartbeat_table(connection)
            db.update_heartbeat_table(
                self.cluster_id, self.name, timestamp, connection
            )
            self.timestamp = timestamp

    def to_dict(self, reset=False):
        """ Return a dictionary describing this object for json dumps

        Returns:
            dict: The object's meta data
        """
        if reset or self._dict is None:
            self._dict = {
                'host': self.host,
                'port': self.port,
                'cluster_id': self.cluster_id,
                'is_slave': self.is_slave,
                'master_name': self.master_name
            }
        return dict(self._dict)