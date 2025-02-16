from peewee import *

from lb_local.model.database import user_db
from lb_local.model.service import Service


class Credential(Model):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "credential"

    service = ForeignKeyField(Service)
    user_name = TextField(null=False)
    salt = TextField(null=False)
    token = TextField(null=False)

    def __repr__(self):
        return "<Credential('%s')>" % (self.user_name or "")
