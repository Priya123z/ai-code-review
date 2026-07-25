Feature: auth.py — AI-suggested coverage

  Scenario: Attempt SQL injection through username parameter
    Given a test database with user 'testuser'
    When login is called with username "testuser' OR '1'='1" and any password
    Then the function should return None or raise an error, not return a valid token

  Scenario: Validate secure password handling
    Given a user with a known password
    When the password is stored and later verified
    Then the plaintext password should not be stored in the database
    And password verification should be constant-time

  Scenario: Validate token generation security
    Given multiple user logins
    When tokens are generated for each user
    Then tokens should be unique and unpredictable
    And tokens should not contain predictable patterns

  Scenario: Test session timeout functionality
    Given a user logs in and receives a token
    When the session expiration time passes
    Then the token should no longer be valid
    And current_user should return None
