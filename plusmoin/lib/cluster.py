import time
from plusmoin.lib import db


class Cluster(object):
    """Represents a cluster of servers

    Attributes:
        cluster_id (int): Cluster ID
        master (Node): The master node, or none.
        slaves (list of Node): The active slave nodes
        lost (list of Node): Nodes that are down or out of sync, but assumed
            to be part of this cluster
        has_master (bool): True if this cluster has a master

    Args:
        cluster_id (int): The ID of the cluster
        max_sync_delay (ind): Maximum sync delay between master and slave
        recover_sync_delay (ind): Maximum sync delay between master and slave
            for a node to come back up.
        master (Node, optional): The master node. Defaults to None.
    """
    def __init__(self, cluster_id, max_sync_delay,
                 recover_sync_delay, master=None):
        self.cluster_id = cluster_id
        self.master = master
        self.timestamp = 0
        self.max_sync_delay = max_sync_delay
        self.recover_sync_delay = recover_sync_delay
        self.slaves = []
        self.lost = []
        self._dict = None

    def update_cluster(self):
        """Update the cluster's node and their status.

        Returns:
            dict: A dictionary defining: {
                    'master_down': False or <Node> if the master went down,
                    'master_up': False or <Node> if a master came up,
                    'slaves_down': [list of <Node> that went down],
                    'slaves_up': [list of <Node> that went up],
                    'out': [list of <Node> that are not part of this cluster
                           anymore]
                }
        """
        new_timestamp = int(time.time())
        new_slaves = []
        new_lost = []
        status = {
            'master_down': False,
            'master_up': False,
            'slaves_down': [],
            'slaves_up': [],
            'out': []
        }
        # Update the master
        if self.has_master:
            self.timestamp = self.master.timestamp
            master_update = self._update_nodes(
                new_timestamp,
                self.max_sync_delay, [self.master]
            )
            if master_update['master'] is None:
                status['master_down'] = self.master
                self.master = None
                new_slaves += master_update['slaves']
                new_lost += master_update['lost']
                status['out'] += master_update['out']

        # Update the slaves
        slave_update = self._update_nodes(
            new_timestamp,
            self.max_sync_delay, self.slaves
        )
        if slave_update['master'] is not None:
            status['master_down'] = False
            status['master_up'] = slave_update['master']
            self.master = slave_update['master']
            self.master.cluster_id = self.cluster_id
        new_slaves += slave_update['slaves']
        new_lost += slave_update['lost']
        status['slaves_down'] += slave_update['lost']
        status['out'] += slave_update['out']

        # Update the lost nodes
        lost_update = self._update_nodes(
            new_timestamp,
            self.recover_sync_delay, self.lost
        )
        if lost_update['master'] is not None:
            status['master_down'] = False
            status['master_up'] = lost_update['master']
            self.master = lost_update['master']
            self.master.cluster_id = self.cluster_id
        new_slaves += lost_update['slaves']
        new_lost += lost_update['lost']
        status['slaves_up'] += lost_update['slaves']
        status['out'] += lost_update['out']

        self.slaves = new_slaves
        self.lost = new_lost

        return status

    def _update_nodes(self, new_timestamp, delay, nodes):
        """Perform an update on a list of nodes and sort them into categories.

        Args:
            new_timestamp (int): The current iteration's timestamp
            delay (int): Acceptable delay to bring a node up or down
            nodes (list of Node): Nodes to perform an update on

        Returns:
            dict: A dictionary including the nodes from the provided list,
                  sorted as:
                {
                    'master': Master Node, or None,
                    'slaves': Nodes that are slaves,
                    'lost':   Nodes that are lost,
                    'out':    Nodes that do not belong here
                }
        """
        new_master = None
        new_slaves = []
        new_lost = []
        new_out = []
        for node in nodes:
            try:
                node.refresh_role()
                if not node.is_slave:
                    if ((self.has_master and self.master != node)
                            or new_master is not None):
                        # We already have a master - go away.
                        new_out.append(node)
                    else:
                        try:
                            # We have a master!
                            node.update_heartbeat(new_timestamp)
                            new_master = node
                        except db.DbError:
                            new_lost.append(node)
                elif self.has_master:
                    node.refresh_info()
                    if self.timestamp - node.timestamp > delay:
                        # Node is out of sync
                        new_lost.append(node)
                    elif node.cluster_id != self.cluster_id:
                        # If the node is in sync, but the cluster_id is wrong
                        # it ought to be elsewhere
                        new_out.append(node)
                    else:
                        new_slaves.append(node)
                else:
                    # We don't have a master - so we can't tell much, but if the
                    # node updates it might belong to somewhere else!
                    prev_ts = node.timestamp
                    node.refresh_info()
                    if node.timestamp != prev_ts and node.cluster_id != self.cluster_id:
                        new_out.append(node)
                    else:
                        new_slaves.append(node)
            except db.DbError as e:
                new_lost.append(node)

        return {
            'master': new_master,
            'slaves': new_slaves,
            'lost': new_lost,
            'out': new_out
        }

    def add_node(self, node):
        """Adds a node to the cluster

        Args:
            node (Node): Node to add

        Raises:
            ValueError: When attempting to add a master to a cluster which
                already has one.
        """
        if not self.has_master:
            if node.is_slave:
                # Without a master, we can't tell if this is in sync or whether
                # it should really be here. So move it to lost for now.
                self.lost.append(node)
            else:
                # We have a new master!
                self.master = node
        else:
            if node.is_slave:
                if self.master.timestamp - node.timestamp <= self.max_sync_delay:
                    if node.master_name == self.master.name:
                        self.slaves.append(node)
                    else:
                        # It's in sync but pointing to the wrong master. Put
                        # it in lost for now.
                        self.lost.append(node)
                else:
                    self.lost.append(node)
            else:
                # We can't have two masters. Reject it.
                raise ValueError()

    @property
    def has_master(self):
        """True if this cluster has a master

        Returns:
            bool: True if this cluster has a master
        """
        return self.master is not None

    def to_dict(self, reset=False):
        """ Return a dictionary describing this object for json dumps

        Returns:
            dict: This object's meta-data
        """
        if reset or self._dict is None:
            self._dict = {
                'cluster_id': self.cluster_id,
                'has_master': self.has_master,
                'slaves': [n.to_dict(reset) for n in self.slaves],
                'lost': [n.to_dict(reset) for n in self.lost]
            }
            if self.has_master:
                self._dict['master'] = self.master.to_dict(reset)
            else:
                self._dict['master'] = None
        return dict(self._dict)
