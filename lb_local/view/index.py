import json
from copy import copy
from urllib.parse import urlparse

from flask import Blueprint, render_template, request, current_app, make_response, session
from flask_login import login_required, current_user
from troi.content_resolver.lb_radio import ListenBrainzRadioLocal
from troi.content_resolver.subsonic import SubsonicDatabase, Database
from troi.content_resolver.top_tags import TopTags
from troi.content_resolver.unresolved_recording import UnresolvedRecordingTracker
from troi.local.periodic_jams_local import PeriodicJamsLocal
from troi.playlist import _deserialize_from_jspf, PlaylistElement
from werkzeug.exceptions import BadRequest, ServiceUnavailable
from lb_local.view.credential import load_credentials

from lb_local.login import login_forbidden

index_bp = Blueprint("index_bp", __name__)


@index_bp.route("/")
@login_required
def index():
    return render_template('index.html')


@index_bp.route("/welcome")
@login_forbidden
def welcome():
    return render_template('login.html', no_navbar=True)


@index_bp.route("/lb-radio", methods=["GET"])
@login_required
def lb_radio_get():
    prompt = request.args.get("prompt", "")
    load_credentials(current_user.user_id)
    t = render_template('lb-radio.html', prompt=prompt, page="lb-radio", subsonic=json.dumps(session["subsonic"]))
    r = make_response(t)
    if session["cors_url"]:
        r.headers.set('Access-Control-Allow-Origin', session["cors_url"])
    return r


@index_bp.route("/lb-radio", methods=["POST"])
@login_required
def lb_radio_post():

    load_credentials(current_user.user_id)
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
    from icecream import ic
    ic(playlist.playlists[0])
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


@index_bp.route("/playlist/create", methods=["POST"])
@login_required
def playlist_create():
    jspf = request.get_json()

    playlist = _deserialize_from_jspf(json.loads(jspf["jspf"]))
    playlist_element = PlaylistElement()
    playlist_element.playlists = [playlist]

    url = urlparse(session["subsonic"]["url"])
    conf = copy(current_app.config)
    conf["SUBSONIC_HOST"] = "%s://%s" % (url.scheme, url.hostname)
    conf["SUBSONIC_PORT"] = int(url.port)

    db = SubsonicDatabase(current_app.config["DATABASE_FILE"], Config(**conf), quiet=False)
    db.open()
    db.upload_playlist(playlist_element)

    return ('', 204)


@index_bp.route("/weekly-jams", methods=["GET"])
@login_required
def weekly_jams_get():
    load_credentials(current_user.user_id)

    t = render_template('weekly-jams.html', page="weekly-jams", subsonic=session["subsonic"])
    r = make_response(t)
    if session["cors_url"]:
        r.headers.set('Access-Control-Allow-Origin', session["cors_url"])
    return r


@index_bp.route("/weekly-jams", methods=["POST"])
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
        raise ServiceUnavailable()

    return render_template('component/playlist-table.html', recordings=recordings, jspf=json.dumps(playlist.get_jspf()))


@index_bp.route("/top-tags", methods=["GET"])
@login_required
def tags():
    db = Database(current_app.config["DATABASE_FILE"], quiet=False)
    db.open()
    tt = TopTags()
    ts = tt.get_top_tags(250)
    return render_template("top-tags.html", tags=ts, page="top-tags")


@index_bp.route("/unresolved", methods=["GET"])
@login_required
def unresolved():
    db = Database(current_app.config["DATABASE_FILE"], quiet=False)
    db.open()
    urt = UnresolvedRecordingTracker()
    return render_template("unresolved.html", unresolved=urt.get_releases(), page="unresolved")
