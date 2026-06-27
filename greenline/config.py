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

# Connection settings for the MySQL server.
#
# Every value can be overridden with an environment variable, so the same code
# runs on different machines without editing this file:
#   - On the developer Mac it defaults to the bundled local server that
#     start_db.sh launches (port 3309, root, no password).
#   - On another computer (e.g. a standard Windows MySQL install on port 3306
#     with a root password), set the GREENLINE_DB_* variables - most commonly
#     just GREENLINE_DB_PORT=3306 and GREENLINE_DB_PASSWORD=your_password - or
#     simply change the defaults below.
DB_CONFIG = {
    "host": os.environ.get("GREENLINE_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("GREENLINE_DB_PORT", "3309")),
    "user": os.environ.get("GREENLINE_DB_USER", "root"),
    "password": os.environ.get("GREENLINE_DB_PASSWORD", ""),
    "database": os.environ.get("GREENLINE_DB_NAME", "greenline"),
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
