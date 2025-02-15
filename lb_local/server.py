import hashlib
from datetime import datetime, timezone
from functools import wraps
import json
import os
import uuid
import validators

from flask import Flask, render_template, request, current_app, redirect, url_for, flash
from flask_cors import CORS
from flask_admin import Admin
from flask_admin.contrib.peewee import ModelView
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from werkzeug.exceptions import BadRequest
from authlib.integrations.flask_client import OAuth
from troi.playlist import _deserialize_from_jspf, PlaylistElement
from troi.content_resolver.subsonic import SubsonicDatabase, Database
from troi.content_resolver.lb_radio import ListenBrainzRadioLocal
from troi.local.periodic_jams_local import PeriodicJamsLocal
from troi.content_resolver.top_tags import TopTags
from troi.content_resolver.unresolved_recording import UnresolvedRecordingTracker
import peewee

from lb_local.database import UserDatabase
from lb_local.model.user import User
from lb_local.model.service import Service
from lb_local.model.database import user_db
import config

# TODO:
# - Pass hints and error messages from content resolver
# - Resolve playlists

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"

login_manager = LoginManager()
login_manager.login_view = ".welcome"

@login_manager.user_loader
def load_user(login_id):
    try:
        return User.select().where(User.login_id == login_id).get()
    except peewee.DoesNotExist:
        return None


def login_forbidden(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_anonymous:
            return redirect(url_for(".index"))
        return f(*args, **kwargs)

    return decorated


def fetch_token():
    return current_user.get_token()


def update_token(name, token, refresh_token=None, access_token=None):
    if refresh_token:
        item = User.select().where(User.name == name, User.refresh_token == refresh_token)
    elif access_token:
        item = User.select().where(User.name == name, User.access_token == access_token)
    else:
        return

    item.access_token = token["access_token"]
    if "refresh_token" in token:
        item.refresh_token = token["refresh_token"]
    item.access_token_expires_at = datetime.fromtimestamp(token["expires_at"], tz=timezone.utc)
    item.save()


class UserModelView(ModelView):

    form_excluded_columns = ('user_id', 'token')

    def is_accessible(self):
        return current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("index", next=request.url))

    def after_model_delete(self, model):
        # TODO: Revoke session for user
        pass

class ServiceModelView(ModelView):

    form_excluded_columns = ('uuid')
    can_create = False

    def is_accessible(self):
        user = session.get('user')
        return user["is_admin"]

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index', next=request.url))


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
                   client_kwargs={"scope": "profile"},
                   authorize_params={"access_type": "offline"},
                   fetch_token=fetch_token)
    admin = Admin(app, name='ListenBrainz Local Admin')
    admin.add_view(UserModelView(User, "User"))
    admin.add_view(ServiceModelView(Service, "Service"))

    login_manager.init_app(app)

    if not exists:
        udb.create()
    else:
        udb.open()

    return app, oauth


app, oauth = create_app()


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
@login_forbidden
def welcome():
    return render_template('login.html', no_navbar=True)


@app.route("/login")
def login_redirect():
    redirect_uri = url_for('auth', _external=True)
    return oauth.musicbrainz.authorize_redirect(redirect_uri)


@app.route('/auth')
def auth():
    token = oauth.musicbrainz.authorize_access_token()

    r = oauth.musicbrainz.get("https://musicbrainz.org/oauth2/userinfo")
    userinfo = r.json()

    try:
        user = User.select().where(User.name == userinfo["sub"]).get()
        user.access_token = token["access_token"]
        user.access_token_expires_at = datetime.fromtimestamp(token["expires_at"], tz=timezone.utc)
        if "refresh_token" in token:
            user.refresh_token = token["refresh_token"]
    except peewee.DoesNotExist:
        if userinfo["sub"] in config.ADMIN_USERS:
            user = User(
                name=userinfo["sub"],
                access_token=token["access_token"],
                refresh_token=token.get("refresh_token"),
                access_token_expires_at=datetime.fromtimestamp(token["expires_at"]),
                login_id=str(uuid.uuid4())
            )
        else:
            flash("Sorry, you do not have an account on this server.")
            return redirect("/welcome")

    user.save()

    login_user(user)

    return redirect("/")


@app.route('/logout')
def logout():
    logout_user()
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

@app.route("/services", methods=["GET"])
@login_required
def services():
    return render_template("services.html", page="services")

@app.route("/services/add", methods=["GET"])
@login_required
def service_add():
    return render_template("service-add.html", mode="Add")

@app.route("/services/<uuid>/edit", methods=["GET"])
@login_required
def service_edit(uuid):
    service = Service.get(Service.uuid == uuid)
    return render_template("service-add.html", mode="Edit", service=service)

@app.route("/services/<uuid>/delete", methods=["GET"])
@login_required
def service_delete(uuid):
    try:
        service = Service.get(Service.uuid == uuid)
        service.delete_instance()
        flash("Service deleted")
    except peewee.DoesNotExist:
        flash("Service %s not found" % uuid)
    except peewee.IntegrityError as err:
        flash("Service still in use and cannot be deleted.")

    return redirect(url_for("services"))

@app.route("/services/add", methods=["POST"])
@login_required
def service_add_post():
    name = request.form.get("name", "")
    url = request.form.get("url", "")
    _uuid = request.form.get("uuid", "")
    if not url or not name:
        flash("Both name and URL are required.")
        return render_template("service-add.html", name=name, url=url)

    if not url.startswith("https://") and not url.startswith("http://"):
        flash("URL must start with http:// or https://")
        return render_template("service-add.html", name=name, url=url)

    if not validators.url(url):
        flash("Invalid URL")
        return render_template("service-add.html", name=name, url=url)

    try:
        if _uuid:
            service = Service.get(uuid=_uuid)
            service.name = name
            service.url = url
        else:
            service = Service.create(name=name, url=url, uuid=uuid.uuid4())
        service.save()
    except peewee.IntegrityError as err:
        flash("Duplicate service name or service URL.")
        return render_template("service-add.html", name=name, url=url)

    return redirect(url_for("services"))

@app.route("/services/list", methods=["GET"])
@login_required
def services_list():
    services = Service.select()
    return render_template("component/services-list.html", services=services)
