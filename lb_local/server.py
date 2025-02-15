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
import peewee

from lb_local.database import UserDatabase
from lb_local.model.user import User
from lb_local.model.service import Service
from lb_local.model.credential import Credential
from lb_local.model.database import user_db
from lb_local.view.admin import UserModelView, ServiceModelView
from lb_local.view.service import service_bp
from lb_local.view.index import index_bp
from lb_local.view.credential import credential_bp
from lb_local.login import load_user, login_forbidden, fetch_token, login_manager, update_token, subsonic_credentials_url_args
import config

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

    CORS(app, origins=[f"{config.SUBSONIC_URL}"])
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

    if not exists:
        udb.create()
    else:
        udb.open()

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
