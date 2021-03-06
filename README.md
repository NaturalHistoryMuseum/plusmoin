plusmoin
========
[![Build Status](https://travis-ci.org/NaturalHistoryMuseum/plusmoin.svg?branch=master)](https://travis-ci.org/NaturalHistoryMuseum/plusmoin) [![Coverage Status](https://img.shields.io/coveralls/NaturalHistoryMuseum/plusmoin.svg)](https://coveralls.io/r/NaturalHistoryMuseum/plusmoin)

*plusmoin* is a daemon to help manage clusters of PostgreSQL servers setup in
master/slave replication.

Given a list of PostgreSQL hosts, *plusmoin* will:

- Identify and keep track of master and slave nodes;
- Keep track of each cluster (one master, multiple slaves);
- Check whether slave nodes are in-sync with their master;
- Run configurable triggers on specific events (eg. master node down,
  slave node down, slave node up, etc. See *plusmoin triggers* for the full
  list of triggers)

plusmoin can be used as a standalone service, or in conjunction with load
balancers such as pgpool2, adding missing functionality (eg. re-attaching 
nodes).

**Warning: plusmoin is under development. If you would like to help developing
it then please give it a try. If you want something that just runs without you
having to worry about it, it's not quite ready yet.**

Understanding *plusmoin*
------------------------

In order to deploy it effectively, it is important to understand how *plusmoin*
works.

*plusmoin* keeps track of multiple types of nodes:
- *master* nodes (for which `pg_is_in_recovery()` returns `false`);
- *slave* nodes (for which `pg_is_in_recovery()` returns `true`) and are known
   to be in sync with their master (at the time the master was last seen); 
- *lost* nodes, which belong to a cluster but are down or known to be
  out of sync with their master (when last seen);
- *cluster-less* nodes, which have a completely unknown status.

*plusmoin* uses a custom table in which it stores, for each master, the name
of the host and a regularly updated timestamp. This table is then accessed via
each slave, allowing *plusmoin* to identify the slave's master, and how far
back the synchronisation is by comparing the timestamp to the master's value.
If the difference in timestamps is higher than a given value, then the slave
node is assumed to be out of sync.

Given a list of hosts, *plusmoin* will:
- Identify all the master servers;
- Identify all the slave servers;
- Group those into clusters.

Clusters try to avoid change:
- A slave node will only leave a cluster if it actively changes master. So
  if the master goes down, the cluster remains;
- If a slave node becomes a master in a cluster without a master, then it
  remains in that cluster as the new master (and the nodes that do not
  update their master entry stay in the cluster, but are assumed to be out of 
  sync);

If a cluster ends up having two masters, then it will be split into two
clusters and their corresponding slaves will follow them. A slave which points
to neither of the masters will remain in the original cluster.

*plusmoin* makes no assumption about what may happen underneath it - nodes can
come and go, change their status from slave to master, or change their master
node.

*plusmoin* triggers
-------------------

*plusmoin* runs a number of triggers when specific events happen. Triggers are
always run *per cluster*, and a single trigger will only known about the nodes
in that cluster (plus the clusterless nodes).

Triggers are invoked without specific parameters, and a JSON object is sent to them via
`stdin`. It is assumed that trigger scripts will be written in a language that
makes reading json easy - but if you must write this in shell, then tools like
[jq](http://stedolan.github.io/jq/) or [jsawk](https://github.com/micha/jsawk)
might come in handy.

Also note that *plusmoin* does not persist it's state - so if it is stopped and
restarted, it will not be able to tell what happened when it was switched off
(which nodes were moved, changed, etc.) and will not run any specific triggers.
Instead it will run a single startup trigger.

The available triggers are:
- `plusmoin_up` which is run when *plusmoin* first starts up;
- `plusmoin_heartbeat` which is run after every iteration, once all nodes have
   been updated and all other triggers been run;
- `master_down` which is run when a master node goes down (or is demoted to
   slave) and there is no replacement master;
- `master_up` which is run when a new master node is available. If the master
  changes within one heartbeat, then this may be invoked without `master_down`
  having been invoked;
- `slave_down` which is run when a slave node goes down or goes out of sync;
- `slave_up` which is run when a slave node is back up and in sync.

The JSON object provided to the scripts has the following structure:

```
{
  "cluster_id": <int>,
  "trigger": null or <node entry>,
  "master": null or <node entry>,
  "slaves": [<node entry>, ...],
  "lost": [<node entry>, ...],
  "clusterless": [<node entry>, ...]
}
```          

Where each node entry is of the form:
```
{
  "host": <str>,
  "port": <int>,
  "cluster_id": <int>,
  "is_slave": <bool>,
  "master_name": <str>
}
```

`trigger` represents the node for which the trigger was run (eg. the 
slave that went down for a `slave_down` trigger)

*plusmoin* running status
-------------------------

As well triggers, *plusmoin* allows applications to directly access the status
of all nodes - allowing developers to create applications that are aware of
*plusmoin*, rather than using a layer of triggers/scripts in between the two. 
The status is stored in a JSON file, by default `/var/run/plusmmoin/status.json`.

This contains a JSON object of the form:

```
  clusters: [
    {
      "cluster_id": <int>,
      "has_master": <bool>,
      "master": null or <node entry>,
      "slaves": [<node entry>, ...],
      "lost": [<node entry>, ...]
    },
    ...
  ],
  "clusterless": [<node entry>, ...]
}
```          

Where each node entry is of the form:
```
{
  "host": <str>,
  "port": <int>,
  "cluster_id": <int>,
  "is_slave": <bool>,
  "master_name": <str>
}
```

The information is updated every heartbeat, so there is no need to query it
more often than the configured heartbeat. *plusmoin* does not make this
available to applications on other hosts. To achieve this, simply serve the
file using a web server of your choice. This can easily be done with a 
one-liner:

```
  cd /var/run/plusmoin && python -m SimpleHTTPServer 8000
```

Preparing your cluster
----------------------
You will, of course, need a cluster of PostgreSQL servers, with slave nodes
replicating from master nodes. *plusmoin* does not mind which replication method
is used, you will just need to configure it to take into account the expected
lag. Each master will need a custom user and database that is used by 
*plusmoin* (see *Understanding plusmoin*). This can be set up as:

```sql
CREATE USER plusmoin WITH UNENCRYPTED PASSWORD 'carrotcake';
CREATE DATABASE plusmoin WITH OWNER plusmoin; 
```

Note that the username, database name and password must be the same for each
cluster managed by a single instance of *plusmoin*. Don't forget to ensure that
`pg_hba.conf` allows (on all servers, masters and slaves) access for that
user from the server that will run *plusmoin*:

```
host    plusmoin        plusmoin        10.0.0.1/32        md5
```

Installing *plusmoin*
---------------------

### Docker

We provide a Docker image for plusmoin. You can get it by doing:

```
docker pull aliceh75/plusmoin:VERSION
```

You will need to create your own image that adds the configuration, and any
triggers you might use. Here is an example Dockerfile you can use to do this:

```
FROM aliceh75/plusmoin:0.1
COPY plusmoin.json /etc/plusmoin/plusmoin.json
COPY slave_up /usr/local/bin/slave_up
# etc.
```

Note that by default *plusmoin* is the main process in the container, and it
will not daemonize, outputing it's log on stdout.

### Manual installation

*plusmoin* is a python application running on Python 2.7. We recommend
installing it in a virtual environment:

```
apt-get install build-essentials python-dev libpq-dev python-virtualenv
virtualenv /usr/lib/plusmoin
cd /usr/lib/plusmoin
. bin/activate
pip install -e git+https://github.com/NaturalHistoryMuseum/plusmoin.git#egg=plusmoin
pip install -r src/plusmoin/requirements.txt  
deactivate
```

*plusmoin* logs into a log file, and stores it's pid and running status in
custom files - by default in `/var/log/plusmoin/plusmoin.log`, 
`/var/run/plusmoin/plusmoin.pid` and `/var/run/plusmoin/status.json`. The
corresponding folders must be created as the user that will be running plusmoin:

```
mkdir /var/log/plusmoin
mkdir /var/run/plusmoin
```

Configuring *plusmoin*
----------------------
By default *plusmoin* expects it's configuration file in 
`/etc/plusmoin/plusmoin.json`. This is a json file, with comments allowed. Here
is an example configuration file detailing all available options:

```
/**
 * Plusmoin configuration. This is a JSON files with comments.
 */
{
  // The name of the database used to store the plusmoin heartbeat table.
  // Must be the same accross all clusters. Required (no default)
  "dbname": "plusmoin",

  // The username to log on to the database server. Must have write access
  // to the plusmoin database. Required (no default)
  "user": "plusmoin",

  // The username to log on to the database server. Must have write access
  // to the plusmoin database. Required (no default)
  "password": "nothing",

  // How often Plusmoin wakes up to perform tests and run triggers, in
  // seconds. Default: 60
  "heartbeat": 60,

  // The maximum acceptable delay between a master and a slave, in seconds.
  // If the delay is longer than this, the slave is assumed to be down.
  // Default: 120
  "max_sync_delay": 120,

  // The maximum acceptable delay to bring a slave back up, in seconds.
  // Having this different from "sync_delay" ensures that nodes that are
  // around the limit won't constantly go up and down. Default: 60
  "recover_sync_delay": 60,

  // List of nodes to manage. Each entry in the list is a dictionary of the
  // form: {"host": "example.com", "port": 5432}. Each entry must be unique.
  // Default: []
  "nodes": [],

  // List of triggers to run, as a dict of trigger name to shell command.
  // Triggers can be ommited or set to None. Defaults to {}
  "triggers": {
    "plusmoin_up": null,
    "plusmoin_heartbeat": null,
    "master_up": null,
    "master_down": null,
    "slave_up": null,
    "slave_down": null
  },

  // Timeout for trigger commands, in seconds. Defaults to 60.
  "trigger_timeout": 60,

  // Log file. Defaults to '/var/log/plusmoin/plusmoin.log'. Ensure that the
  // directory exists and is writeable by the plusmoin daemon user.
  "log_file": "/var/log/plusmoin/plusmoin.log",

  // Log level, one of 'error', 'info' and 'debug'. Defaults to 'error'
  "log_level": "error",

  // User the daemon should run as. Defaults to 'nobody'
  "daemon_user": "nobody",

  // Pid file where the PID is stored. Defaults to
  // '/var/run/plusmoin/plusmoin.pid'. Ensure that the directory exists and is
  // writeable by the plusmoin daemon user.
  "pid_file": "/var/run/plusmoin/plusmoin.pid",

  // File where the running status is stored, as a json objects. Defaults to
  // '/var/run/plusmoin/status.json'. Ensure that the directory exists and is
  // writeable by the plusmoin daemon user.
  "status_file": "/var/run/plusmoin/status.json",

  // Connection timeout for databases, in seconds, Default: 60
  "connect_timeout": 60,

  // SQL statement which should return TRUE if the node on which it is run is
  // a slave. Defaults to "SELECT pg_is_in_recovery()"
  "is_slave_statement": "SELECT pg_is_in_recovery()"
}
```

Testing *plusmoin*
------------------

*plusmoin* has a set of unit tests which can be run by doing:

```python setup.py nosetests```

In addition *plusmoin* has a set of functional tests. Because these rely on
Docker to run clusters of PostgreSQL servers they cannot be executed on our
CI server so are run separately as a manual process. Note that you should
install `docker-py`:

```
pip install docker-py
```

You must run the tests as root. To run each scenario, simply do:

```
python plusmoin/tests/functional/scenario1.py
```

As long as no exception is raised, then the tests passed (connection errors
will be shown on stdout, but these are expected and part of the error log).
