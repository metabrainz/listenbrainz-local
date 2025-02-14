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

    id = IntegerField(null=False, unique=True)
    name = TextField(null=False, unique=True)
    token = TextField(null=False)

    def __repr__(self):
        return "<User('%d %s')>" % (self.id, self.name or "")
