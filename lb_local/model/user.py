from flask_login import UserMixin
from peewee import *

import config
from lb_local.model.database import user_db


class User(Model, UserMixin):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "user"

    user_id = AutoField(primary_key=True)
    login_id = TextField(null=True, unique=True)
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
        return self.name in config.ADMIN_USERS

    def __repr__(self):
        return "<User('%s' '%s')>" % (self.user_id, self.name or "")
