import datetime
from peewee import *
from lb_local.model.database import user_db


class User(Model):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "user"

    user_id = IntegerField()
    name = TextField(null=False, unique=True)
    token = TextField()

    def __repr__(self):
        return "<User('%d %s')>" % (self.id, self.name or "")
