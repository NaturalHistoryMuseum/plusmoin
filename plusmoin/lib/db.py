import logging
import psycopg2
import traceback
from contextlib import contextmanager
from plusmoin.config import config


class DbError(Exception):
    """Exception raised when database errors are encountered.

    In all cases this
    means that the status of the server is unknown and should be considered
    as lost or down
    """
    pass


@contextmanager
def get_connection(host, port):
    """Create and yield a new database connection to the given host/port

    Args:
        host (str): Hostname of the server
        port (int): Port of the server

    Yields:
        psycopg2.connection: The database connection

    Raises:
        DbError: On any error (timeout, credentials, etc.)
    """
    details = {
        'host': host,
        'port': port,
        'user': config['user'],
        'password': config['password'],
        'dbname': config['dbname'],
        'connect_timeout': config['connect_timeout']
    }
    try:
        connection = psycopg2.connect(**details)
    except psycopg2.Error as e:
        # Can be no server, wrong credentials, timeout, etc.
        logger = logging.getLogger()
        logger.error("Could not connect to {}:{}: {}".format(
            host, port, traceback.format_exc()
        ))
        raise DbError()
    try:
        yield connection
    finally:
        connection.close()


def is_slave(connection):
    """Check if the given connection represents a master or slave database

    Args:
        connection (psycopg2.connection): The database connection

    Returns:
        bool: True if this is a slave, false otherwise

    Raises:
        DbError: On any database error
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(config['is_slave_statement'])
            value = cursor.fetchone()
            if value is None or len(value) != 1:
                raise DbError()
            return value[0]
    except psycopg2.Error as e:
        logger = logging.getLogger()
        logger.error("Could not determine slave status: {}".format(e.pgerror))
        raise DbError()


def get_info(connection):
    """Returns the cluster id, master and timestamp of a node

    Args:
        connection (psycopg2.connection): The database connection

    Returns:
        Tuple containing (cluster id, master name, timestamp)

    Raises:
        DbError: On all database errors
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT cluster_id, master, tstamp FROM heartbeat
            """)
            value = cursor.fetchone()
            if not value or len(value) != 3:
                raise DbError()
            return value[0], value[1], value[2]
    except psycopg2.Error as e:
        logger = logging.getLogger()
        logger.error("Could not get node info: {}".format(e.pgerror))
        raise DbError()


def create_heartbeat_table(connection):
    """Create heartbeat table if it doesn't exist, and populate a default entry

    Args:
        connection (psycopg2.connection): Database connection object

    Raises:
        DbError: On all database errors
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
              CREATE TABLE IF NOT EXISTS heartbeat(cluster_id INT,
                                                   master TEXT,
                                                   tstamp BIGINT)
            """)
            cursor.execute('SELECT COUNT(*) FROM heartbeat')
            value = cursor.fetchone()
            if value[0] == 0:
                cursor.execute("""
                  INSERT INTO heartbeat(cluster_id, master, tstamp)
                              VALUES(%s, %s, %s)
                """, (-1, '-', 0))
            connection.commit()
    except psycopg2.Error as e:
        logger = logging.getLogger()
        logger.error("Could not create heartbeat table: {}".format(e.pgerror))
        raise DbError()


def update_heartbeat_table(cluster_id, name, timestamp, connection):
    """Update the heartbeat table

    Args:
        cluster_id (int): The new cluster id
        name (str): The new master name
        timestamp (int): The new timestamp
        connection (psycopg2.connection): The database connection object

    Raises:
        DbError: On all database errors
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
              UPDATE heartbeat SET
                cluster_id = %s,
                master = %s,
                tstamp = %s
            """, (cluster_id, name, timestamp))
            connection.commit()
    except psycopg2.Error as e:
        logger = logging.getLogger()
        logger.error("Could not create heartbeat table: {}".format(e.pgerror))
        raise DbError()
