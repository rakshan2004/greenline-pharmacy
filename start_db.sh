#!/bin/bash
# Starts the local, project-private MySQL server that Greenline Pharmacy uses.
#
# The database lives entirely inside this project folder (.mysql_data) and runs
# on port 3309 so it never clashes with any other MySQL on the machine. On the
# first run it initialises a fresh, password-less data directory (the system is
# meant to be zero-cost and self-contained, per the client's budget concern).
# Running the script again simply starts the existing server if it is down.

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MYSQLD="/Users/rakshanrajeshjagadeesan/Documents/cs105/anaconda3/bin/mysqld"
MYSQL="/Users/rakshanrajeshjagadeesan/Documents/cs105/anaconda3/bin/mysql"
DATADIR="$PROJECT_DIR/.mysql_data"
SOCK="$DATADIR/mysql.sock"
PORT=3309

# If our server already answers, there is nothing to do.
if [ -S "$SOCK" ] && "$MYSQL" --socket="$SOCK" -uroot -e "SELECT 1" >/dev/null 2>&1; then
  echo "Greenline MySQL is already running on port $PORT."
  exit 0
fi

# Initialise the data directory the first time only.
if [ ! -d "$DATADIR/mysql" ]; then
  echo "Initialising Greenline database files..."
  mkdir -p "$DATADIR"
  "$MYSQLD" --no-defaults --initialize-insecure --datadir="$DATADIR"
fi

# Launch the server in the background, logging to server.log.
echo "Starting Greenline MySQL on port $PORT..."
nohup "$MYSQLD" --no-defaults --datadir="$DATADIR" --socket="$SOCK" \
  --port=$PORT --bind-address=127.0.0.1 > "$DATADIR/server.log" 2>&1 &

# Wait until it accepts connections, then create the application database.
for i in $(seq 1 30); do
  if "$MYSQL" --socket="$SOCK" -uroot -e "SELECT 1" >/dev/null 2>&1; then
    "$MYSQL" --socket="$SOCK" -uroot -e "CREATE DATABASE IF NOT EXISTS greenline CHARACTER SET utf8mb4;"
    echo "Greenline MySQL is ready on port $PORT."
    exit 0
  fi
  sleep 1
done

echo "MySQL did not start in time. Check $DATADIR/server.log"
exit 1
