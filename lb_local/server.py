import atexit
import os
import uuid
from datetime import datetime

import peewee
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, url_for, flash
from flask_admin import Admin
from flask_admin.contrib.peewee import ModelView
from flask_cors import CORS
from flask_login import login_user, logout_user

import config
from lb_local.database import UserDatabase
from lb_local.login import fetch_token, login_manager
from lb_local.model.credential import Credential
from lb_local.model.service import Service
from lb_local.model.user import User
from lb_local.view.admin import UserModelView, ServiceModelView
from lb_local.view.credential import credential_bp, load_credential
from lb_local.view.index import index_bp
from lb_local.view.service import service_bp
from lb_local.sync import SyncManager

# TODO:
# - Pass hints and error messages from content resolver
# - Resolve playlists

STATIC_PATH = "/static"
STATIC_FOLDER = "static"
TEMPLATE_FOLDER = "templates"


def create_app():
    exists = os.path.exists(config.USER_DATABASE_FILE)
    udb = UserDatabase(config.USER_DATABASE_FILE, False)

    app = Flask(__name__, static_url_path=STATIC_PATH, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
    app.config.from_object('config')

    # UPdate with credentials from config
    CORS(app)
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
    admin.add_view(ModelView(Credential, "Credential"))

    login_manager.init_app(app)

    sync_manager = SyncManager()
    sync_manager.start()
    app.config["SYNC_MANAGER"] = sync_manager

    if not exists:
        udb.create()
    else:
        udb.open()
        
    return app, oauth

app, oauth = create_app()
app.register_blueprint(index_bp)
app.register_blueprint(service_bp, url_prefix="/service")
app.register_blueprint(credential_bp, url_prefix="/credential")

#    print("got teardown request")
#    if app.config["SYNC_MANAGER"] is not None:
#        app.config["SYNC_MANAGER"].exit()
#    app.config["SYNC_MANAGER"] = None

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
        if userinfo["sub"] in config.ADMIN_USERS:
            user = User(name=userinfo["sub"],
                        access_token=token["access_token"],
                        refresh_token=token.get("refresh_token"),
                        access_token_expires_at=datetime.fromtimestamp(token["expires_at"], tz=None))
        else:
            flash("Sorry, you do not have an account on this server.")
            return redirect("/welcome")

    user.save()

    login_user(user)
    load_credential()

    return redirect("/")


@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')
