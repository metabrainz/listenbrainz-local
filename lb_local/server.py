import logging
import os
import sys
from time import sleep
from datetime import datetime
import multiprocessing
from threading import get_ident
import signal

import peewee
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, url_for, flash, current_app
from flask_admin import Admin
from flask_admin.contrib.peewee import ModelView
from flask_cors import CORS
from flask_login import login_user, logout_user
from dotenv import dotenv_values

from lb_local.database import UserDatabase
from lb_local.login import fetch_token, login_manager
from lb_local.model.credential import Credential
from lb_local.model.service import Service
from lb_local.model.user import User
from lb_local.view.admin import UserModelView, ServiceCredentialModelView
from lb_local.view.credential import credential_bp, load_credentials
from lb_local.view.index import index_bp
from lb_local.view.service import service_bp
from lb_local.sync import SyncManager
from troi.content_resolver.subsonic import SubsonicDatabase

# TODO:
# - New feature: Import and Resolve playlists
# Saving playlists from mixed services is undefined
# sync errors cause jobs to be stuck and not removed from queue.
# Fix mobile views
# Fix Auth
# Support funkwhale

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"

env_keys = ["DATABASE_FILE", "SECRET_KEY", "DOMAIN", "PORT", "AUTHORIZED_USERS", "SERVICE_USERS",
            "MUSICBRAINZ_CLIENT_ID", "MUSICBRAINZ_CLIENT_SECRET"]

submit_queue = multiprocessing.Queue()
stats_req_queue = multiprocessing.Queue()
stats_queue = multiprocessing.Queue()
stop_event = multiprocessing.Event()
sync_manager = None
manager_owner_tid = None

class Config:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def signal_handler(signum, frame):
    if sync_manager is not None and get_ident() == manager_owner_tid:
        stop_event.set()
        sync_manager.join()
        os._exit(0)
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def create_app():
    
    global sync_manager
    
    app = Flask(__name__, static_url_path=STATIC_PATH, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)

    # Load the .env file config    
    env_config = dotenv_values(".env")
    
    # Have the docker-compose file override any settings from .env
    for k in env_keys:
        if k in os.environ:
            env_config[k] = os.environ[k]
            
        if k not in env_config:
            app.logger.error("Setting '%s' must be defined in .env file." % k)
            sys.exit(-1)
            
    env_config["AUTHORIZED_USERS"] = [ x.strip() for x in env_config["AUTHORIZED_USERS"].split(",") ]
    env_config["ADMIN_USERS"] = [ x.strip() for x in env_config["ADMIN_USERS"].split(",") ]
    env_config["SERVICE_USERS"] = [ x.strip() for x in env_config["SERVICE_USERS"].split(",") ]
    app.config.from_mapping(env_config)

    db_file = app.config["DATABASE_FILE"]
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
    
    # Configure Flask-Admin with authentication
    from flask_admin import Admin, AdminIndexView
    from flask_login import current_user
    from werkzeug.exceptions import Forbidden
    
    class AuthenticatedAdminIndexView(AdminIndexView):
        def is_accessible(self):
            return current_user.is_authenticated and current_user.is_admin
            
        def inaccessible_callback(self, name, **kwargs):
            from flask import redirect, url_for, request
            if not current_user.is_authenticated:
                return redirect(url_for("index_bp.index", next=request.url))
            else:
                raise Forbidden()
    
    admin = Admin(app, name='ListenBrainz Local Admin', index_view=AuthenticatedAdminIndexView(), template_mode='bootstrap3')
    admin.add_view(UserModelView(User, "User"))
    admin.add_view(ServiceCredentialModelView(Service, "Service"))
    admin.add_view(ServiceCredentialModelView(Credential, "Credential"))

    login_manager.init_app(app)

    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN'):
        manager_owner_tid = get_ident()
        sync_manager = SyncManager(submit_queue, stats_req_queue, stats_queue, stop_event, db_file)
        #sync_manager.start()

    app.config["STATS_QUEUE"] = stats_queue
    app.config["STATS_REQ_QUEUE"] = stats_req_queue
    app.config["SUBMIT_QUEUE"] = submit_queue
    app.config["STOP_EVENT"] = stop_event
        
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
