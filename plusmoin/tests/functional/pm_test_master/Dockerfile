FROM ubuntu:12.04

#
# Install postgresql
#
RUN apt-get update && apt-get install -y postgresql-9.1

#
# Setup configuration & restart
#
RUN /bin/echo -e "                                           \
        host    all             all     0.0.0.0/0   md5   \n \
        host    replication     all     0.0.0.0/0   trust \n \
    " >> /etc/postgresql/9.1/main/pg_hba.conf                \
    && /bin/echo -e "                                        \
        listen_addresses = '*'                            \n \
        port = 5432                                       \n \
        wal_level = hot_standby                           \n \
        max_wal_senders = 3                               \n \
        wal_keep_segments = 256                           \n \
    " >> /etc/postgresql/9.1/main/postgresql.conf            \
    && /etc/init.d/postgresql restart

#
# Create the plusmoin user and database
#
USER postgres
RUN /etc/init.d/postgresql start                                          \
    && psql -c "CREATE USER plusmoin WITH UNENCRYPTED PASSWORD 'secret';" \
    && psql -c "CREATE DATABASE plusmoin WITH OWNER plusmoin;"

EXPOSE 5432
CMD /usr/lib/postgresql/9.1/bin/postgres -D /var/lib/postgresql/9.1/main -c config_file=/etc/postgresql/9.1/main/postgresql.conf
