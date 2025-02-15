import datetime
from peewee import *
from lb_local.model.database import user_db


class Service(Model):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "service"

    name = TextField(null=False, unique=True)
    url = TextField(null=False, unique=True)
    uuid = TextField(null=False)

    def __repr__(self):
        return "<Service('%s')>" % (self.name or "")
