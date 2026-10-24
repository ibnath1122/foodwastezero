"""Create the database, tables and demo data.

    python setup_db.py            # (re)creates everything with demo data
    python setup_db.py --empty    # tables + admin user only, no demo data

WARNING: this drops and recreates the FoodWasteZero tables.
"""
import os
import sys

import config
import db as dbm
from seed import seed


def run_script(conn_db, path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # strip "-- comment" lines, then split into statements
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    for stmt in "\n".join(lines).split(";"):
        if stmt.strip():
            conn_db.execute(stmt)


def database_ready():
    """True if the database and its tables already exist."""
    try:
        d = dbm.DB(dbm.connect())
        d.scalar("SELECT COUNT(*) FROM users")
        d.close()
        return True
    except Exception:
        return False


def main(empty=None):
    here = os.path.dirname(os.path.abspath(__file__))
    if empty is None:
        empty = "--empty" in sys.argv

    if config.DB_ENGINE == "sqlite":
        schema = os.path.join(here, "database", "schema_sqlite.sql")
        conn = dbm.connect()
    else:
        schema = os.path.join(here, "database", "schema.sql")
        try:
            conn = dbm.connect(with_database=False)
        except Exception as e:
            print("\nCould not connect to MySQL at %s:%s as '%s'." % (config.MYSQL_HOST, config.MYSQL_PORT, config.MYSQL_USER))
            print("Start MySQL in the XAMPP Control Panel and try again.\nDetails:", e)
            sys.exit(1)

    d = dbm.DB(conn)
    print("Creating tables ...")
    run_script(d, schema)
    if config.DB_ENGINE != "sqlite":
        d.execute("USE %s" % config.MYSQL_DB)

    if empty:
        from werkzeug.security import generate_password_hash
        d.execute("INSERT INTO users (username, password_hash, full_name) VALUES (%s,%s,%s)",
                  ("admin", generate_password_hash("admin123"), "Store Manager"))
        print("Created empty database with admin user.")
    else:
        print("Seeding demo data ...")
        seed(d)
        d.commit()
        print("Demo data loaded.")
    d.close()
    print("\nDone.  Login:  admin / admin123\nNow run:  python app.py")


if __name__ == "__main__":
    main()
