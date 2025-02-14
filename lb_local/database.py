import logging
import os

import peewee

from lb_local.model.database import db, setup_db
from lb_local.model.user import User

logger = logging.getLogger(__name__)


class Database:
    '''
    Keep a database with metadata for a collection of local music files.
    '''

    def __init__(self, db_file, quiet):
        self.db_file = db_file
        self.quiet = quiet

    def create(self):
        """
            Create the database. Can be run again to create tables that have been recently added to the code,
            but don't exist in the DB yet.
        """
        try:
            db_dir = os.path.dirname(os.path.realpath(self.db_file))
            os.makedirs(db_dir, exist_ok=True)
            setup_db(self.db_file)
            db.connect()
            db.create_tables((
                User,
            ))
        except Exception as e:
            logger.error("Failed to create db file %r: %s" % (self.db_file, e))

    def open(self):
        """
            Open the database file and connect to the db.
        """
        try:
            setup_db(self.db_file)
            db.connect()
        except peewee.OperationalError:
            logger.error("Cannot open database index file: '%s'" % self.db_file)
            sys.exit(-1)

    def close(self):
        """ Close the db."""
        db.close()
