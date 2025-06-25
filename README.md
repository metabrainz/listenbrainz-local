# listenbrainz-local

ListenBrainz local brings recommendation features to your local Subsonic hosted music collection. Many subsonic projects
lack recommendations or good playlisting tools and this project aims to create another layer on top of these projects to show
what can actually be done when you have lots of good music metadata. 

Note: **Your collection must be tagged with MBIDs in order for this project to work.** Please do not open any
bug reports asking us to make ListenBrainz Local work with an untagged collection. We will *never* do this.

Support for LB Radio and Weekly jams exists now -- music playback and saving playlists to the subsonic hosts are now working and many other recommendation tools will be added over time. 

This project is a web app that requires a subsonic hosted music collection:

* [Funkwhale](https://www.funkwhale.audio/)
* [Gonic](https://github.com/sentriz/gonic)
* [Navidrome](https://www.navidrome.org/)

So far we've only tested with Navidrome, so we would appreciate help testing others setups.

## Important Security Consideration

Due to the current state of the services (navidrome, etc) not all of these services are currently
supporting strong auth that does not pass plaintext passwords. The ListenBrainz team is actively
contributing to these projects, but this process isn't complete yet.

In the meantime **password are stored in plaintext in the database and passed in plaintext to
the front-end**. 

Clearly we will fix this as soon as we are able.


# Installation

We recommend the Docker setup for users who wish run this service; if you want to do development
a python virtual environment setup is better.

## Docker Setup

First, make sure you have Docker installed and correctly setup. ( https://docs.docker.com/engine/install/ )

Second, clone this repo and then in the listenbrainz-local directory create a file called .env
that contains the following configuration lines:

```
SECRET_KEY="any string of your choice"
ADMIN_USERS=<comma separated list of LB username that should be admins to setup lb-local.>
DOMAIN=<the fully qualified domain where lb-local will be available, without port number>
PORT=<the port numer where lb-local will be available>
MUSICBRAINZ_CLIENT_ID=<MB client id, see https://musicbrainz.org/account/applications >
MUSICBRAINZ_CLIENT_SECRET=<MB client secret, see https://musicbrainz.org/account/applications >
```

Note: Put values in "" if the values contain spaces.

When adding a MusicBrainz application, create the application here: https://musicbrainz.org/account/applications .
For 'Callback URI' enter:

http://<domain>[:<port>]/auth -> http://mydomain.com:500/auth

Then continue with:

```
docker compose build && docker compose up
```

And LB Local will be available at the specified DOMAIN:PORT specified above!

## Docker Setup with Encryption (TLS)

If you wish to also create a proxy with TLS (https) support, then follow the steps above, but also
add the following to your .env file:

```
EMAIL=<your email address>
```

The PORT configuration will be ignored in this setup and port 443 will be used.

Then start the service with:

```
docker compose build && docker compose up
```

## Development setup

Currently it is easy to run the app from the command line, so that is the recommended approach for development:

```
cp config.py.sample config.py
vim config.py
<edit config -- see above for details on what value to put>
python3 -mvenv .virtualenv
source .virtualenv/bin/activate
pip install -r requirements.txt
./lb_local.py
```

The app should then be available at the URL configured in config.py.


# Screenshot

![screenshot](/misc/lb-local-screenshot.png)
