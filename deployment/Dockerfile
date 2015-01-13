FROM ubuntu:12.04

#
# Install Python & virtualenv
#
RUN apt-get update && apt-get install -y python python-virtualenv git build-essential python-dev libpq-dev

#
# Install plusmoin & dependencies in a virtualenv.
#
RUN virtualenv /usr/lib/plusmoin                                              \
    && cd /usr/lib/plusmoin                                                   \
    && . /usr/lib/plusmoin/bin/activate                                       \
    && pip install -e git+https://github.com/NaturalHistoryMuseum/plusmoin.git#egg=plusmoin  \
    && pip install -r /usr/lib/plusmoin/src/plusmoin/requirements.txt         \
    && mkdir /etc/plusmoin                                                    \
    && mkdir /var/run/plusmoin                                                \
    && mkdir /var/log/plusmoin

COPY config.json /etc/plusmoin/config.json
CMD /usr/lib/plusmoin/bin/plusmoin start -x
