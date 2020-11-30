ARG PYTHON_VERSION=3.8

###
### Stage 0: builder
###
FROM docker.io/python:${PYTHON_VERSION}-slim as builder

# install the OS build deps
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libjpeg-dev \
    libpq-dev \
    libssl-dev \
    libwebp-dev \
    libxml++2.6-dev \
    libxslt1-dev \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# Build dependencies that are not available as wheels, to speed up rebuilds
RUN python -m pip install --prefix="/install" --no-warn-script-location \
        frozendict \
        jaeger-client \
        opentracing \
        psycopg2 \
        pycparser \
        pyrsistent \
        pyyaml \
        simplejson \
        threadloop \
        thrift
###
### Stage 1: runtime
###

ENV PYTHONUNBUFFERED=1
RUN mkdir /synapse
RUN mkdir /scripts


RUN mkdir /data
WORKDIR /data

RUN pip install matrix-synapse