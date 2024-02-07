import json

from flask import Flask, render_template, request, current_app
from werkzeug.exceptions import BadRequest

from troi.playlist import _deserialize_from_jspf, PlaylistElement
from troi.content_resolver.content_resolver import ContentResolver
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


# TODO:
# - Fix parsing of artist mbids from jspf in troi
# - Pass hints and error messages from content resolver
# - Resolve playlists


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/lb-radio", methods=["GET"])
def lb_radio_get():

    prompt = request.args.get("prompt", "")
    return render_template('lb-radio.html', prompt=prompt)


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

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], current_app.config)
    db.open()
    r = ListenBrainzRadioLocal()
    playlist = r.generate(mode, prompt, .8)
    try:
        recordings = playlist.playlists[0].recordings
    except (IndexError, KeyError, AttributeError):
        # TODO: Display this on the web page
        db.metadata_sanity_check(include_subsonic=upload_to_subsonic)
        return

    return render_template('playlist-table.html', recordings=recordings, jspf=json.dumps(playlist.get_jspf()))


class Config:

    def __init__(self, **entries):
        self.__dict__.update(entries)


@app.route("/playlist/create", methods=["POST"])
def playlist_create():
    jspf = request.get_json()

    playlist = _deserialize_from_jspf(json.loads(jspf["jspf"]))
    playlist_element = PlaylistElement()
    playlist_element.playlists = [playlist]

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], Config(**current_app.config))
    db.open()
    db.upload_playlist(playlist_element)

    return ('', 204)


@app.route("/weekly-jams", methods=["GET"])
def weekly_jams_get():
    return render_template('weekly-jams.html')


@app.route("/weekly-jams", methods=["POST"])
def weekly_jams_post():

    try:
        user_name = request.form["user_name"]
    except KeyError:
        raise BadRequest("argument 'user_name' is required.")

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], current_app.config)
    db.open()
    r = PeriodicJamsLocal(user_name, .8)
    playlist = r.generate()
    try:
        recordings = playlist.playlists[0].recordings
    except (IndexError, KeyError, AttributeError):
        return

    return render_template('playlist-table.html', recordings=recordings, jspf=json.dumps(playlist.get_jspf()))


@app.route("/top-tags", methods=["GET"])
def tags():
    db = Database(current_app.config["DATABASE_FILE"])
    db.open()
    tt = TopTags()
    tags = tt.get_top_tags(250)
    return render_template("top-tags.html", tags=tags)


@app.route("/unresolved", methods=["GET"])
def unresolved():
    db = Database(current_app.config["DATABASE_FILE"])
    db.open()
    urt = UnresolvedRecordingTracker()
    return render_template("unresolved.html", unresolved=urt.get_releases())
