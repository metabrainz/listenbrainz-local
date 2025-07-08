from peewee import *

from lb_local.model.database import user_db
from lb_local.model.user import User

class Service(Model):
    """
       Store user information
    """

    class Meta:
        database = user_db
        table_name = "service"

    owner = ForeignKeyField(User)
    slug = TextField(null=False, unique=True)
    url = TextField(null=False, unique=True)
    status = TextField(null=True)
    last_synched = IntegerField(null=True)
    scan_log = TextField(null=True)

    def __repr__(self):
        return "<Service('%s')>" % (self.name or "")
