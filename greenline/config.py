"""Central configuration values for the Greenline Pharmacy application.

Keeping every "magic" value (database credentials, app name, business rules)
in one module means the rest of the codebase never hard-codes these settings,
so changing the database port or the expiry-warning window is a one-line edit
here rather than a hunt through the whole project.
"""

import os

# Absolute path to the folder that contains this file's parent (the project
# root). It is computed at runtime so the app works no matter where the
# project folder is moved to on disk.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Connection settings for the local MySQL server. The server is started from
# start_db.sh on a non-standard port (3309) using a project-local data
# directory, so these values match that script. Password is empty because the
# server was initialised with --initialize-insecure for a self-contained,
# zero-cost setup (the client asked for a freeware / no-extra-cost system).
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3309,
    "user": "root",
    "password": "",
    "database": "greenline",
    # Reconnect automatically if the connection drops while the GUI is idle.
    "autocommit": False,
}

# Human-facing application name, reused in window titles and headings.
APP_NAME = "Greenline Pharmacy"
APP_TAGLINE = "Inventory, Receivables & Reporting"

# Business rule: a medicine batch is treated as "expiring soon" when its expiry
# date is within this many days of today. Used to highlight rows in amber and
# to drive the dashboard expiry alerts (Criteria A, Appendix 1 point 9).
EXPIRY_WARNING_DAYS = 30

# Business rule: stock at or below a medicine's reorder level counts as
# "running low" and is flagged so the client knows to restock.
DEFAULT_REORDER_LEVEL = 20
