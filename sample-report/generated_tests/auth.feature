Feature: auth.py, AI-suggested coverage

  Scenario: Login fails with SQL‑injection payload
    Given a user "alice" with password "wonderland" exists in the database
    When the login function is called with username "alice' OR '1'='1" and any password
    Then the function returns None (authentication fails)

  Scenario: Token does not expose secret key
    Given a user "bob" with password "builder" exists
    When login is called with correct credentials
    Then the returned token does not contain the SECRET_KEY value

  Scenario: Login succeeds with correct password and fails with wrong password when passwords are hashed
    Given a user "carol" with password "s3cr3t" stored as a bcrypt hash in the database
    When login is called with username "carol" and password "s3cr3t"
    Then login returns a token
    When login is called with username "carol" and password "wrong"
    Then login returns None
