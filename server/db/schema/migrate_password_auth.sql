-- Adds username/passwordHash to Users for password-based login. Run once
-- against an existing database created from an older schema.sql.
--
-- Existing rows predate both columns, so they're backfilled with a username
-- derived from the name plus the userId (unique by construction) and an
-- empty hash. An empty hash never matches a candidate password, so those
-- accounts can't be logged into until a password is set for them.
USE portfolio_manager;

ALTER TABLE Users
    ADD COLUMN username VARCHAR(32) NOT NULL DEFAULT '' AFTER userId,
    ADD COLUMN passwordHash VARCHAR(255) NOT NULL DEFAULT '';

UPDATE Users
    SET username = CONCAT(LOWER(firstName), userId)
    WHERE username = '';

ALTER TABLE Users
    ADD UNIQUE KEY uniqueUsername (username),
    ALTER COLUMN username DROP DEFAULT,
    ALTER COLUMN passwordHash DROP DEFAULT;
