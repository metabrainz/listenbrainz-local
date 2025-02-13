import hashlib
import json
import uuid


from flask import Flask, render_template, request, current_app, redirect, session, url_for
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from authlib.integrations.flask_client import OAuth

from troi.playlist import _deserialize_from_jspf, PlaylistElement
from troi.content_resolver.subsonic import SubsonicDatabase, Database
from troi.content_resolver.lb_radio import ListenBrainzRadioLocal
from troi.local.periodic_jams_local import PeriodicJamsLocal
from troi.content_resolver.top_tags import TopTags
from troi.content_resolver.unresolved_recording import UnresolvedRecordingTracker
import config

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"

app = Flask(__name__, static_url_path=STATIC_PATH, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
app.config.from_object('config')
CORS(app, origins=[f"{config.SUBSONIC_HOST}:{config.SUBSONIC_PORT}"])
oauth = OAuth(app)
oauth.register(
    name='musicbrainz',
    authorize_url="https://musicbrainz.org/oauth2/authorize",
    redirect_uri="http://127.0.0.1:5000/auth",
    access_token_url="https://musicbrainz.org/oauth2/token",
    client_kwargs={
        'scope': 'profile'
    }
)

# TODO:
# - Fix parsing of artist mbids from jspf in troi
# - Pass hints and error messages from content resolver
# - Resolve playlists

def subsonic_credentials_url_args():
    """Return the subsonic API request arguments that must be appended to a subsonic call."""

    salt = str(uuid.uuid4())
    h = hashlib.new('md5')
    h.update(bytes(config.SUBSONIC_PASSWORD, "utf-8"))
    h.update(bytes(salt, "utf-8"))
    token = h.hexdigest()
    return { "args":f"u={config.SUBSONIC_USER}&s={salt}&t={token}&v=1.14.0&c=lb-local", "host":config.SUBSONIC_HOST, "port":config.SUBSONIC_PORT }

@app.route("/")
def index():
    user = session.get('user')
    if user is None:
        return render_template('login.html', no_navbar=True)
    else:
        return render_template('index.html')

@app.route("/login")
def login_redirect():
    redirect_uri = url_for('auth', _external=True)
    return oauth.musicbrainz.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = oauth.musicbrainz.authorize_access_token()
    ## Save the token in the DB, not the user session
    session['user'] = token['access_token']
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route("/lb-radio", methods=["GET"])
def lb_radio_get():

    prompt = request.args.get("prompt", "")
    return render_template('lb-radio.html', prompt=prompt, page="lb-radio", subsonic=subsonic_credentials_url_args())


@app.route("/lb-radio", methods=["POST"])
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

    return render_template('playlist-table.html', recordings=recordings,
                           jspf=json.dumps(playlist.get_jspf()))


class Config:

    def __init__(self, **entries):
        self.__dict__.update(entries)


@app.route("/playlist/create", methods=["POST"])
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
def weekly_jams_get():
    return render_template('weekly-jams.html', page="weekly-jams", subsonic=subsonic_credentials_url_args())


@app.route("/weekly-jams", methods=["POST"])
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

    return render_template('playlist-table.html', recordings=recordings, jspf=json.dumps(playlist.get_jspf()))


@app.route("/top-tags", methods=["GET"])
def tags():
    db = Database(current_app.config["DATABASE_FILE"], quiet=False)
    db.open()
    tt = TopTags()
    tags = tt.get_top_tags(250)
    return render_template("top-tags.html", tags=tags, page="top-tags")


@app.route("/unresolved", methods=["GET"])
def unresolved():
    db = Database(current_app.config["DATABASE_FILE"], quiet=False)
    db.open()
    urt = UnresolvedRecordingTracker()
    return render_template("unresolved.html",
                           unresolved=urt.get_releases(),
                           page="unresolved")
