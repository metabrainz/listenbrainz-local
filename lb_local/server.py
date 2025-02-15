import hashlib
from functools import wraps
import json
import os
import uuid

from flask import Flask, render_template, request, current_app, redirect, session, url_for, flash
from flask_cors import CORS
from flask_admin import Admin
from flask_admin.contrib.peewee import ModelView
from werkzeug.exceptions import BadRequest
from authlib.integrations.flask_client import OAuth
from authlib.integrations.flask_oauth2 import ResourceProtector
from troi.playlist import _deserialize_from_jspf, PlaylistElement
from troi.content_resolver.subsonic import SubsonicDatabase, Database
from troi.content_resolver.lb_radio import ListenBrainzRadioLocal
from troi.local.periodic_jams_local import PeriodicJamsLocal
from troi.content_resolver.top_tags import TopTags
from troi.content_resolver.unresolved_recording import UnresolvedRecordingTracker
import peewee

from lb_local.database import UserDatabase
from lb_local.model.user import User
from lb_local.model.database import user_db
import config

# TODO:
# - Pass hints and error messages from content resolver
# - Resolve playlists

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"


# oauth2: The authlib docs state that I need to be providing a fetch_token function, but it never gets called.
def fetch_token(name):
    print("fetch token called for %s" % name)
    try:
        user = User.select().where(User.name == name).get()
        print("found existing user")
    except peewee.DoesNotExist:
        return None

    return user['token'].to_token()

class LBLocalModelView(ModelView):

    def is_accessible(self):
        user = session.get('user')
        return user["is_admin"]

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index', next=request.url))

    def after_model_delete(self, model):
        # TODO: Revoke session for user
        pass


def create_app():
    exists = os.path.exists(config.USER_DATABASE_FILE)
    udb = UserDatabase(config.USER_DATABASE_FILE, False)

    app = Flask(__name__, static_url_path=STATIC_PATH, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
    app.config.from_object('config')

    CORS(app, origins=[f"{config.SUBSONIC_HOST}:{config.SUBSONIC_PORT}"])
    oauth = OAuth(app, fetch_token=fetch_token)
    oauth.register(name='musicbrainz',
                   authorize_url="https://musicbrainz.org/oauth2/authorize",
                   redirect_uri=config.DOMAIN + "/auth",
                   access_token_url="https://musicbrainz.org/oauth2/token",
                   client_kwargs={'scope': 'profile'})
    admin = Admin(app, name='ListenBrainz Local Admin')
    admin.add_view(LBLocalModelView(User, user_db))

    if not exists:
        udb.create()
    else:
        udb.open()

    return (app, oauth)


app, oauth = create_app()


# oauth2: the docs are unclear if a resourceprotector should be used for clients as well as servers? But
# the decorator as implemented is clearly incomplete. Do I even need this decorator?
# https://docs.authlib.org/en/latest/client/flask.html#accessing-oauth-resources
# is unclear and I am not sure what part is flask fantasy and what is reality
#require_oauth = ResourceProtector()
def login_required(func):

    @wraps(func)
    def wrapper():
        user = session.get('user')
        if user is None:
            print("Found no session, redirect to login")
            return redirect("/welcome")

        print("Found session")
        return func()

    return wrapper


def subsonic_credentials_url_args():
    """Return the subsonic API request arguments that must be appended to a subsonic call."""

    salt = str(uuid.uuid4())
    h = hashlib.new('md5')
    h.update(bytes(config.SUBSONIC_PASSWORD, "utf-8"))
    h.update(bytes(salt, "utf-8"))
    token = h.hexdigest()
    return {
        "args": f"u={config.SUBSONIC_USER}&s={salt}&t={token}&v=1.14.0&c=lb-local",
        "host": config.SUBSONIC_HOST,
        "port": config.SUBSONIC_PORT
    }


@app.route("/")
@login_required
def index():
    return render_template('index.html')


@app.route("/welcome")
def welcome():
    return render_template('login.html', no_navbar=True)


@app.route("/login")
def login_redirect():
    redirect_uri = url_for('auth', _external=True)
    return oauth.musicbrainz.authorize_redirect(redirect_uri)


@app.route('/auth')
def auth():
    token = oauth.musicbrainz.authorize_access_token()

    r = oauth.musicbrainz.get('https://musicbrainz.org/oauth2/userinfo')
    userinfo = r.json()

    try:
        user = User.select().where(User.name == userinfo["sub"]).get()
        user.token = token['access_token']
    except peewee.DoesNotExist:
        flash("Sorry, login denied.")
        return redirect("/welcome")

    user.save()

    session['user'] = {
        "user_name": userinfo["sub"],
        "user_id": userinfo["metabrainz_user_id"],
        "is_admin": userinfo["sub"] in config.ADMIN_USERS
    }
    return redirect('/')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


@app.route("/lb-radio", methods=["GET"])
@login_required
def lb_radio_get():

    prompt = request.args.get("prompt", "")
    return render_template('lb-radio.html', prompt=prompt, page="lb-radio", subsonic=subsonic_credentials_url_args())


@app.route("/lb-radio", methods=["POST"])
@login_required
def lb_radio_post():

    try:
        prompt = request.form["prompt"]
    except KeyError:
        raise BadRequest("argument 'prompt' is required.")

    try:
        mode = request.form["mode"]
    except KeyError:
        raise BadRequest("argument 'mode' is required.")

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], current_app.config, quiet=False)
    db.open()
    r = ListenBrainzRadioLocal(quiet=False)
    playlist = r.generate(mode, prompt, .8)
    try:
        recordings = playlist.playlists[0].recordings
    except (IndexError, KeyError, AttributeError):
        # TODO: Display this on the web page
        db.metadata_sanity_check(include_subsonic=True)
        return

    return render_template('component/playlist-table.html', recordings=recordings, jspf=json.dumps(playlist.get_jspf()))


class Config:

    def __init__(self, **entries):
        self.__dict__.update(entries)


@app.route("/playlist/create", methods=["POST"])
@login_required
def playlist_create():
    jspf = request.get_json()

    playlist = _deserialize_from_jspf(json.loads(jspf["jspf"]))
    playlist_element = PlaylistElement()
    playlist_element.playlists = [playlist]

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], Config(**current_app.config), quiet=False)
    db.open()
    db.upload_playlist(playlist_element)

    return ('', 204)


@app.route("/weekly-jams", methods=["GET"])
@login_required
def weekly_jams_get():
    return render_template('weekly-jams.html', page="weekly-jams", subsonic=subsonic_credentials_url_args())


@app.route("/weekly-jams", methods=["POST"])
@login_required
def weekly_jams_post():

    try:
        user_name = request.form["user_name"]
    except KeyError:
        raise BadRequest("argument 'user_name' is required.")

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], current_app.config, quiet=False)
    db.open()
    r = PeriodicJamsLocal(user_name, .8, quiet=False)
    playlist = r.generate()
    try:
        recordings = playlist.playlists[0].recordings
    except (IndexError, KeyError, AttributeError):
        return

    return render_template('component/playlist-table.html', recordings=recordings, jspf=json.dumps(playlist.get_jspf()))


@app.route("/top-tags", methods=["GET"])
@login_required
def tags():
    db = Database(current_app.config["DATABASE_FILE"], quiet=False)
    db.open()
    tt = TopTags()
    tags = tt.get_top_tags(250)
    return render_template("top-tags.html", tags=tags, page="top-tags")


@app.route("/unresolved", methods=["GET"])
@login_required
def unresolved():
    db = Database(current_app.config["DATABASE_FILE"], quiet=False)
    db.open()
    urt = UnresolvedRecordingTracker()
    return render_template("unresolved.html", unresolved=urt.get_releases(), page="unresolved")
