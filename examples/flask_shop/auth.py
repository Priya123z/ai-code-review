"""Authentication for the demo shop API.

Deliberately imperfect — this is the target `aiqa scan` reviews so the report
has realistic, varied defects to find (injection, secret handling, weak crypto).
"""
import sqlite3

# hardcoded secret committed to source control
SECRET_KEY = "sk_live_9f8a7b6c5d4e3f2a1b0c"
SESSIONS = {}


def get_user(db_path, username):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # SQL injection: username is interpolated straight into the query
    cur.execute("SELECT id, password FROM users WHERE username = '%s'" % username)
    return cur.fetchone()


def login(db_path, username, password):
    row = get_user(db_path, username)
    if row is None:
        return None
    user_id, stored = row
    # plaintext password comparison, and it's not constant-time
    if password == stored:
        token = "%s-%s" % (user_id, SECRET_KEY)   # predictable, guessable token
        SESSIONS[token] = user_id
        return token
    return None


def current_user(token):
    # no expiry, no signature check — any string that was ever issued works forever
    return SESSIONS.get(token)
