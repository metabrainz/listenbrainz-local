from peewee import *

from lb_local.model.database import user_db
from lb_local.model.service import Service
from lb_local.model.user import User


class Credential(Model):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "credential"
        indexes = ((('service', 'user_name'), True),)

    owner = ForeignKeyField(User)
    service = ForeignKeyField(Service)
    user_name = TextField(null=False)
    password = TextField(null=False)
    shared = BooleanField(null=False)


    def __repr__(self):
        return "<Credential('%s' %d)>" % (self.user_name or "", self.shared)
