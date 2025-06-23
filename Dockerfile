FROM metabrainz/python:3.13

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
                       build-essential \
                       git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /code
WORKDIR /code

RUN pip3.13 install setuptools uwsgi

RUN mkdir /code/lb-local
WORKDIR /code/lb-local

COPY requirements.txt /code/lb-local
RUN pip3.13 install --no-cache-dir -r requirements.txt

RUN apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    apt-get clean -y

# Now install our code, which may change frequently
COPY . /code/lb-local/

CMD uwsgi --gid=www-data --uid=www-data --http-socket :3031 \
          --vhost --module=server --callable=app --chdir=/code/lb-local \
          --enable-threads --processes=15
