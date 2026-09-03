"""AI-suggested tests for auth.py. Review, wire fixtures, then run."""

def test_login_sql_injection_prevention(tmp_path):
    db = tmp_path / 'test.db'
    # setup DB with a user
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)')
    conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('alice', 'wonderland'))
    conn.commit()
    conn.close()
    token = login(str(db), "alice' OR '1'='1", 'any')
    assert token is None


def test_token_is_not_predictable(tmp_path):
    db = tmp_path / 'test.db'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)')
    conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('bob', 'builder'))
    conn.commit()
    conn.close()
    token = login(str(db), 'bob', 'builder')
    assert token is not None
    assert 'sk_live_' not in token  # SECRET_KEY should not appear in token

