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
    status = TextField(null=True)
    last_scanned = IntegerField(null=True)
    scan_log = TextField(null=True)

    # This will contain the text for the last scanned field. Can I do this?
    last_scanned_text = None

    def __repr__(self):
        return "<Service('%s')>" % (self.name or "")
