-- Run this once to create the database
-- Then let SQLAlchemy create the tables via db.create_all()

CREATE DATABASE IF NOT EXISTS buyme CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'buyme_user'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON buyme.* TO 'buyme_user'@'localhost';
FLUSH PRIVILEGES;

-- If using root (for local dev), just run:
-- CREATE DATABASE buyme;
-- and update SQLALCHEMY_DATABASE_URI in app.py accordingly
