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
from werkzeug.exceptions import BadRequest, ServiceUnavailable, Forbidden
from lb_local.view.credential import load_credentials

from lb_local.login import login_forbidden

index_bp = Blueprint("index_bp", __name__)


@index_bp.route("/")
@login_required
def index():
    config, msg = load_credentials(current_user.user_id)
    return render_template('index.html', credentials_msg=msg)

@index_bp.route("/welcome")
@login_forbidden
def welcome():
    return render_template('login.html', no_navbar=True)


@index_bp.route("/lb-radio", methods=["GET"])
@login_required
def lb_radio_get():
    prompt = request.args.get("prompt", "")
    title = request.args.get("title", "");
    load_credentials(current_user.user_id)
    t = render_template('lb-radio.html', 
                        prompt=prompt, 
                        title=title, 
                        page="lb-radio",
                        subsonic=json.dumps(session["subsonic"]))
    r = make_response(t)
    if session["cors_url"]:
        r.headers.set('Access-Control-Allow-Origin', session["cors_url"])
    return r


@index_bp.route("/lb-radio", methods=["POST"])
@login_required
def lb_radio_post():

    credential, msg = load_credentials(current_user.user_id)
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
    r = ListenBrainzRadioLocal(quiet=True)
    try:
        playlist = r.generate(mode, prompt, .8)
    except RuntimeError as err:
        return render_template('component/playlist-table.html', errors=str(err))

    try:
        recordings = playlist.playlists[0].recordings
    except (IndexError, KeyError, AttributeError):
        msgs = db.metadata_sanity_check(include_subsonic=True, return_as_array=True)
        return render_template('component/playlist-table.html', errors="\n".join(msgs))
    
    avail_services = []
    services = credential["SUBSONIC_SERVERS"]
    for service in services:
        print(services[service])
        if current_user.user_id == services[service]["owner_id"]:
            avail_services.append(service)

    return render_template('component/playlist-table.html',
                           recordings=recordings,
                           playlist_name=playlist.playlists[0].name,
                           playlist_desc=playlist.playlists[0].description,
                           hints=r.patch.user_feedback(),
                           jspf=json.dumps(playlist.get_jspf()),
                           services=avail_services)


class Config:
    def __init__(self, **entries):
        self.__dict__.update(entries)


@index_bp.route("/playlist/create", methods=["POST"])
@login_required
def playlist_create():
    jdata = request.get_json()
    playlist_jspf = jdata["jspf"]
    service = jdata["service"]
    playlist_name = jdata["playlist-name"]

    playlist = _deserialize_from_jspf(json.loads(playlist_jspf))
    playlist_element = PlaylistElement()
    playlist_element.playlists = [playlist]

    conf, msg = load_credentials(current_user.user_id)
    try:
        if conf["SUBSONIC_SERVERS"][service]["shared"] and \
           conf["SUBSONIC_SERVERS"][service]["owner_id"] != current_user.user_id:
            raise Forbidden
    except KeyError:
        raise Forbidden
        
    try:
        db = SubsonicDatabase(current_app.config["DATABASE_FILE"], Config(**conf), quiet=True)
        db.open()
        db.upload_playlist(playlist_element, service, playlist_name)
    except RuntimeError as err:
        return render_template('component/playlist-save-result.html', error=err)

    return render_template('component/playlist-save-result.html', success="Playlist saved.")


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
    try:
        playlist = r.generate()
    except RuntimeError as err:
        return render_template('component/playlist-table.html', errors=str(err))
    try:
        recordings = playlist.playlists[0].recordings
    except (IndexError, KeyError, AttributeError):
        msgs = db.metadata_sanity_check(include_subsonic=True, return_as_array=True)
        return render_template('component/playlist-table.html', errors="\n".join(msgs))
    
    return render_template('component/playlist-table.html',
                           recordings=recordings,
                           playlist_name=playlist.playlists[0].name,
                           playlist_desc=playlist.playlists[0].description,
                           hints=r.patch.user_feedback(),
                           services=session["subsonic"].keys(),
                           jspf=json.dumps(playlist.get_jspf()))


@index_bp.route("/top-tags", methods=["GET"])
@login_required
def tags():
    db = Database(current_app.config["DATABASE_FILE"], quiet=True)
    db.open()
    tt = TopTags()
    ts = tt.get_top_tags(250)
    return render_template("top-tags.html", tags=ts, page="top-tags")


@index_bp.route("/unresolved", methods=["GET"])
@login_required
def unresolved():
    db = Database(current_app.config["DATABASE_FILE"], quiet=True)
    db.open()
    urt = UnresolvedRecordingTracker()
    return render_template("unresolved.html", unresolved=urt.get_releases(), page="unresolved")
