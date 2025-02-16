import hashlib
import uuid
from datetime import datetime, timezone
from functools import wraps

import peewee
from flask import redirect, url_for
from flask_login import current_user, LoginManager

from lb_local.model.user import User

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
