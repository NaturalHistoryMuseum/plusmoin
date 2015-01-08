FROM ubuntu:12.04

#
# Install postgresql
#
RUN apt-get update && apt-get install -y postgresql-9.1

#
# Setup configuration
#
RUN /bin/echo -e "                                               \
        host    all             all     0.0.0.0/0   md5      \n  \
        host    replication     all     0.0.0.0/0   trust    \n  \
    " >> /etc/postgresql/9.1/main/pg_hba.conf                    \
    && /bin/echo -e "                                            \
        listen_addresses = '*'                               \n  \
        port=5432                                            \n  \
        hot_standby = on                                     \n  \
    " >> /etc/postgresql/9.1/main/postgresql.conf                \
    && /bin/echo -e "                                            \
        standby_mode='on'                                    \n  \
        primary_conninfo = 'host=pg_master port=5432' \n  \
        trigger_file = '/tmp/trigger_file0'                  \n  \
    " > /var/lib/postgresql/9.1/main/recovery.conf

#
# Add startup script. This will perform initial replication and start
# the server. This must be run with the master server running and linked
# at pg_master
#
COPY run.sh /var/lib/postgresql/9.1/run.sh

USER postgres
EXPOSE 5432
CMD /var/lib/postgresql/9.1/run.sh
