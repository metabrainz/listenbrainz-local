import atexit
import os
from datetime import datetime
import signal

import peewee
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, url_for, flash, current_app
from flask_admin import Admin
from flask_admin.contrib.peewee import ModelView
from flask_cors import CORS
from flask_login import login_user, logout_user

from lb_local.database import UserDatabase
from lb_local.login import fetch_token, login_manager
from lb_local.model.credential import Credential
from lb_local.model.service import Service
from lb_local.model.user import User
from lb_local.view.admin import UserModelView, ServiceModelView
from lb_local.view.credential import credential_bp, load_credentials
from lb_local.view.index import index_bp
from lb_local.view.service import service_bp
from lb_local.sync import SyncManager
from troi.content_resolver.subsonic import SubsonicDatabase

try:
    import config
    have_config = True
except ImportError:
    have_config = False
    

# TODO:
# - Adding credentials requirs ADMIN access. Is that smart?
# - Import and Resolve playlists

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"

sync_manager = SyncManager()
sync_manager.daemon = True
sync_manager.start()

class Config:
    def __init__(self, **entries):
        self.__dict__.update(entries)

def signal_handler(signum, frame):
    global sync_manager
    if sync_manager is not None:
        sync_manager.exit()
    sync_manager = None
    raise KeyboardInterrupt
    
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def create_app():

    app = Flask(__name__, static_url_path=STATIC_PATH, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
    if have_config:
        app.config.from_object('config')

    env_config = {} 
    for k in ("DATABASE_FILE", "SECRET_KEY", "DOMAIN", "PORT", "AUTHORIZED_USERS",
              "MUSICBRAINZ_CLIENT_ID", "MUSICBRAINZ_CLIENT_SECRET", "MUSICBRAINZ_BASE_URL"):
        if k in os.environ:
            if k == "AUTHORIZED_USERS":
                env_config[k] = [ x.strip() for x in os.environ[k].split(",") ]
            else:
                env_config[k] = os.environ[k]
            
    if env_config:
        app.config.from_mapping(env_config)

    db_file = app.config["DATABASE_FILE"]
    print(db_file)
    exists = os.path.exists(db_file)
    udb = UserDatabase(db_file, False)
    if not exists:
        print("Database does not exist, creating tables")
        udb.create()
        db = SubsonicDatabase(app.config["DATABASE_FILE"], Config(**{}), quiet=False)
        db.create()
    else:
        print("Database exists, opening...")
        udb.open()

    # UPdate with credentials from config
    CORS(app)
    oauth = OAuth(app, fetch_token=fetch_token)
    oauth.register(name='musicbrainz',
                   authorize_url="https://musicbrainz.org/oauth2/authorize",
                   redirect_uri="%s:%s/auth" % (app.config["DOMAIN"], app.config["PORT"]),
                   access_token_url="https://musicbrainz.org/oauth2/token",
                   client_kwargs={"scope": "profile"},
                   authorize_params={"access_type": "offline"},
                   fetch_token=fetch_token)
    admin = Admin(app, name='ListenBrainz Local Admin')
    admin.add_view(UserModelView(User, "User"))
    admin.add_view(ServiceModelView(Service, "Service"))
    admin.add_view(ModelView(Credential, "Credential"))

    login_manager.init_app(app)

    app.config["SYNC_MANAGER"] = sync_manager

        
    return app, oauth

app, oauth = create_app()
app.register_blueprint(index_bp)
app.register_blueprint(service_bp, url_prefix="/service")
app.register_blueprint(credential_bp, url_prefix="/credential")

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
        user.access_token_expires_at = datetime.fromtimestamp(token["expires_at"], tz=None)
        if "refresh_token" in token:
            user.refresh_token = token["refresh_token"]
    except peewee.DoesNotExist:
        if userinfo["sub"] in current_app.config["AUTHORIZED_USERS"]:
            user = User(name=userinfo["sub"],
                        access_token=token["access_token"],
                        refresh_token=token.get("refresh_token"),
                        access_token_expires_at=datetime.fromtimestamp(token["expires_at"], tz=None))
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
