import datetime
from peewee import *
from lb_local.model.database import user_db
from lb_local.model.service import Service


class Credentials(Model):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "credentials"

    service = ForeignKeyField(Service)
    user = TextField(null=False)
    salt = TextField(null=False)
    token = TextField(null=False)

    def __repr__(self):
        return "<Service('%s')>" % (self.name or "")
