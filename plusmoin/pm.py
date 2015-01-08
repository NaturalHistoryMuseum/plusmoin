import time
import json

from plusmoin.config import config
from plusmoin.lib.node import Node
from plusmoin.lib.cluster import Cluster
from plusmoin.lib.db import DbError
from plusmoin.lib.trigger import trigger


class Plusmoin(object):
    """Represents the running service"""
    def __init__(self, nodes, max_sync_delay, recover_sync_delay):
        self.max_sync_delay = max_sync_delay
        self.recover_sync_delay = recover_sync_delay
        self.clusters = []
        self.clusterless = []
        (masters, slaves, self.clusterless) = self._partition_nodes(nodes)
        self._create_clusters(masters)
        time.sleep(self.max_sync_delay)
        self._assign_slaves(slaves, by_name=True)

    def update_nodes(self):
        """ Refresh all nodes and move them around accordingly

        Returns:
            dict: A dict defining the triggers to invoke for given clusters, eg.
                {
                    'master_down': [(<trigger Node>, <Cluster>),
                                    (<trigger Node>, <Cluster>),
                                    ...
                                   ],
                    ...
                }
        """
        triggers = {
            'master_down': [],
            'master_up': [],
            'slave_down': [],
            'slave_up': []
        }

        # Update all the clusters
        for cluster in self.clusters:
            status = cluster.update_cluster()
            self.clusterless += status['out']
            if status['master_down']:
                triggers['master_down'].append(
                    (status['master_down'], cluster)
                )
            if status['master_up']:
                triggers['master_up'].append((status['master_up'], cluster))
            for node in status['slaves_down']:
                triggers['slave_down'].append((node, cluster))
            for node in status['slaves_up']:
                triggers['slave_up'].append((node, cluster))

        # Create new clusters for each working master in clusterless
        (masters, slaves, self.clusterless) = self._partition_nodes(
            self.clusterless
        )
        self._create_clusters(masters)
        self._assign_slaves(slaves)
        return triggers

    def _partition_nodes(self, nodes):
        """Partition nodes into masters, slaves and clusterless nodes.

        This will invoke refresh_role on all nodes.

        Args:
            nodes (list of Node): The nodes to partition

        Returns:
            Tuple of lists (masters, slaves, clusterless)
        """
        slaves = []
        masters = []
        lost = []
        for node in nodes:
            try:
                node.refresh_role()
                if node.is_slave:
                    slaves.append(node)
                else:
                    masters.append(node)
            except DbError:
                lost.append(node)
        return masters, slaves, lost

    def _create_clusters(self, nodes):
        """ Create new clusters from the given list of masters

        Notes:
            - This will invoke update_heartbeat on all the masters, so the
              cluster will only be created if the right cluster_id is entered
              in the database;
            - Nodes that fail to run update_heartbeat are added to the
              clusterless nodes.

        Args:
            nodes (list of Node): Master nodes to create the clusters from
        """
        timestamp = int(time.time())
        for node in nodes:
            node.cluster_id = len(self.clusters)
            try:
                node.update_heartbeat(timestamp)
                self.clusters.append(Cluster(
                    cluster_id=len(self.clusters),
                    max_sync_delay=self.max_sync_delay,
                    recover_sync_delay=self.recover_sync_delay,
                    master=node
                ))
            except DbError:
                self.clusterless.append(node)

    def _assign_slaves(self, slaves, by_name=False):
        """Assign slave nodes to the correct cluster

        Note:
            - Nodes that did not match a cluster are added to clusterless.

        Args:
            slaves (list of Node): Slaves to assign to the clusters
            clusters (list of Cluster): Clusters, indexed by cluster id
            by_name (bool, optional): If True, rely on the master name (rather
                than the cluster id) to identify the correct cluster. This is
                needed when starting up, as cluster ids from a previous run
                won't be meaningful. But in all other cases, the cluster id
                should be used to ensure clusters remain grouped. Defaults to
                False.
        """
        # Prepare a name index if needed
        if by_name:
            clusters_by_name = {}
            for cluster in self.clusters:
                clusters_by_name[cluster.master.name] = cluster
        # Assign slaves to clusters
        for node in slaves:
            try:
                node.refresh_info()
            except DbError:
                # We'll accept a stale entry at this point.
                pass
            if by_name and node.master_name in clusters_by_name:
                clusters_by_name[node.master_name].add_node(node)
            elif not by_name and 0 <= node.cluster_id < len(self.clusters):
                self.clusters[node.cluster_id].add_node(node)
            else:
                self.clusterless.append(node)


def run():
    """ The main application entry point """
    # Prepare nodes and create Plusmoin object
    nodes = []
    for node_def in config['nodes']:
        nodes.append(Node(node_def['host'], node_def['port']))
    pm = Plusmoin(
        nodes,
        config['max_sync_delay'],
        config['recover_sync_delay']
    )
    # Run initial trigger
    for cluster in pm.clusters:
        info = cluster.to_dict(reset=True)
        info['trigger'] = None
        info['clusterless'] = [n.to_dict(reset=True) for n in pm.clusterless]
        trigger('plusmoin_up', json.dumps(info))
    # Enter the loop
    while True:
        # Wait and run update
        time.sleep(config['heartbeat'])
        triggers = pm.update_nodes()
        # Refresh json representation of nodes and clusters
        clusterless_dict = [n.to_dict(reset=True) for n in pm.clusterless]
        for cluster in pm.clusters:
            cluster.to_dict(reset=True)
        # Run triggers
        for trg in triggers:
            for node, cluster in triggers[trg]:
                info = cluster.to_dict()
                if node:
                    info['trigger'] = node.to_dict()
                else:
                    info['trigger'] = None
                info['clusterless'] = clusterless_dict
                trigger(trg, json.dumps(info))
        for cluster in pm.clusters:
            info = cluster.to_dict()
            info['clusterless'] = clusterless_dict
            trigger('plusmoin_heartbeat', json.dumps(info))
        # Output status
        with open(config['status_file'], 'w') as f:
            f.write(json.dumps({
                'clusters': [c.to_dict() for c in pm.clusters],
                'clusterless': [n.to_dict() for n in pm.clusterless]
            }))
