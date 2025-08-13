from peewee import SqliteDatabase

PRAGMAS = (
    ('foreign_keys', 1),
    ('journal_mode', 'WAL'),
)

user_db = SqliteDatabase(None, pragmas=PRAGMAS)

def setup_db(db_file):
    user_db.init(db_file)
