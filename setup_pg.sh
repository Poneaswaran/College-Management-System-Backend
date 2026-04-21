#!/bin/bash
# Run this in WSL to set up PostgreSQL for the CMS project
# Usage: bash setup_pg.sh

set -e

echo "=== PostgreSQL Setup for College Management System ==="

# Try to create user (works with peer auth as postgres)
sudo -u postgres createuser -d cms_user 2>/dev/null && echo "Created user: cms_user" || echo "User cms_user already exists (OK)"

# Set password for cms_user
sudo -u postgres psql -c "ALTER USER cms_user WITH PASSWORD 'cms_password';" && echo "Password set for cms_user"

# Create database
sudo -u postgres createdb -O cms_user cms_db 2>/dev/null && echo "Created database: cms_db" || echo "Database cms_db already exists (OK)"

echo ""
echo "=== Done! PostgreSQL is ready. ==="
echo "Connection: host=localhost port=5432 dbname=cms_db user=cms_user password=cms_password"
