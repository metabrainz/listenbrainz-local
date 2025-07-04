import uuid

from flask import current_app
from flask_login import UserMixin
from peewee import *

from lb_local.model.database import user_db


class User(Model, UserMixin):
    """
       Store user information
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) 
        from lb_local.server import app
        with app.app_context():
            self.admin_user = current_app.config["AUTHORIZED_USERS"]

    class Meta:
        database = user_db
        table_name = "user"

    user_id = AutoField(primary_key=True)
    login_id = TextField(null=True, unique=True, default=lambda: str(uuid.uuid4()))
    name = TextField(null=False, unique=True)
    access_token = TextField(null=True)
    refresh_token = TextField(null=True)
    # sqlite doesn't have a native datetime type and peewee doesn't automatically parse datetime strings to
    # python datetime objects if they contain a timezone offset, easiest workaround is to always convert
    # utc first and save as a timezone-naive datetime value
    access_token_expires_at = DateTimeField(null=True)

    def get_id(self):
        return self.login_id

    def get_token(self):
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": "Bearer",
            "expires_at": int(self.access_token_expires_at.timestamp()) if self.access_token_expires_at else None,
        }

    @property
    def is_admin(self):
        return self.name in self.admin_users

    def __repr__(self):
        return "<User('%s' '%s')>" % (self.user_id, self.name or "")
