#!/bin/sh
#
# Snapshot the initial database
#
/usr/bin/pg_basebackup -h pg_master -p 5432 -D /var/lib/postgresql/9.1/main2 -U postgres -v -P -x
cp /var/lib/postgresql/9.1/main/recovery.conf /var/lib/postgresql/9.1/main2
cp /var/lib/postgresql/9.1/main/server.* /var/lib/postgresql/9.1/main2
rm -Rf /var/lib/postgresql/9.1/main
mv /var/lib/postgresql/9.1/main2 /var/lib/postgresql/9.1/main
chown -R postgres:postgres /var/lib/postgresql/9.1/main

#
# Start the postgresql server
#
/usr/lib/postgresql/9.1/bin/postgres -D /var/lib/postgresql/9.1/main -c config_file=/etc/postgresql/9.1/main/postgresql.conf
