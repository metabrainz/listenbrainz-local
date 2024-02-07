FROM metabrainz/python:3.10

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
                       build-essential git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /code
WORKDIR /code

RUN pip3.10 install setuptools uwsgi

RUN mkdir /code/lblocal
WORKDIR /code/lblocal

COPY requirements.txt /code/lblocal
RUN pip3.10 install --no-cache-dir -r requirements.txt

RUN apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    apt-get clean -y

# Now install our code, which may change frequently
COPY . /code/lblocal

CMD uwsgi --gid=www-data --uid=www-data --http-socket :3031 \
          --vhost --module=lb_local.server --callable=app --chdir=/code/lblocal \
          --enable-threads --processes=15
