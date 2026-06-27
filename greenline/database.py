"""Database access layer for Greenline Pharmacy.

This module is the single place that talks to MySQL. Every other part of the
program (the UI views) goes through the small Database class below instead of
opening its own connection, which keeps connection handling in one spot and
guarantees a consistent, relational data model (chosen over flat files in
Criteria A so records can be linked without redundant copying).

It also owns the schema definition (init_schema) and a set of realistic demo
rows (seed_demo_data) so the application has something to show on first run.
"""

import datetime
import mysql.connector

from greenline import config
from greenline import auth


class Database:
    """A thin convenience wrapper around a single MySQL connection.

    The wrapper exposes four small helpers (fetch_all, fetch_one, execute,
    executemany). The views build their own SQL strings and call these, which
    keeps each view independent while still funnelling all access through one
    connection object.
    """

    def __init__(self):
        # Open the connection using the central config. A dictionary cursor is
        # requested per-query so rows come back as {column: value} dicts, which
        # read far more clearly in the UI code than tuples.
        #
        # The target database may not exist yet on a fresh machine, so we first
        # connect WITHOUT selecting a database, create it if necessary, and only
        # then open the real connection against it. This removes any need for a
        # separate "create the database" step (important on Windows, where the
        # Mac-only start_db.sh does not run).
        cfg = dict(config.DB_CONFIG)
        db_name = cfg.pop("database")
        bootstrap_conn = mysql.connector.connect(**cfg)
        cur = bootstrap_conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS %s CHARACTER SET utf8mb4" % db_name)
        cur.close()
        bootstrap_conn.close()

        # Now connect with the database selected and keep this as the live link.
        cfg["database"] = db_name
        self.conn = mysql.connector.connect(**cfg)

    def _cursor(self, dictionary=True):
        # Internal helper that hands back a fresh cursor. ping(reconnect=True)
        # silently re-establishes the link if MySQL dropped an idle connection
        # while the user was reading the screen.
        self.conn.ping(reconnect=True, attempts=3, delay=1)
        return self.conn.cursor(dictionary=dictionary)

    def fetch_all(self, sql, params=()):
        # Run a SELECT and return every matching row as a list of dicts.
        cur = self._cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetch_one(self, sql, params=()):
        # Run a SELECT expected to match at most one row; return it or None.
        cur = self._cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def execute(self, sql, params=()):
        # Run an INSERT/UPDATE/DELETE, commit it, and return the new primary key
        # (lastrowid) so callers can immediately reference the row they created.
        cur = self._cursor()
        cur.execute(sql, params)
        self.conn.commit()
        new_id = cur.lastrowid
        cur.close()
        return new_id

    def executemany(self, sql, seq_of_params):
        # Run the same statement for many parameter tuples in one commit, used
        # by the demo seeding to insert lots of rows efficiently.
        cur = self._cursor()
        cur.executemany(sql, seq_of_params)
        self.conn.commit()
        cur.close()

    def close(self):
        # Close the underlying connection when the application exits.
        try:
            self.conn.close()
        except Exception:
            pass


# Each entry is a CREATE TABLE statement. They are ordered so that a table is
# always created after any table its foreign keys point at. The relational
# links (supplier_id, clinic_id, medicine_id) are what let reports join data
# together without duplicating it.
SCHEMA_STATEMENTS = [
    # Staff accounts. Passwords are never stored in plain text: only a salted
    # PBKDF2 hash and its salt are kept, satisfying the client's request to
    # protect supplier prices from prying eyes (Appendix 1 point 7).
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id       INT AUTO_INCREMENT PRIMARY KEY,
        username      VARCHAR(50)  NOT NULL UNIQUE,
        password_hash VARCHAR(128) NOT NULL,
        salt          VARCHAR(64)  NOT NULL,
        full_name     VARCHAR(100) NOT NULL,
        role          VARCHAR(30)  NOT NULL DEFAULT 'representative',
        created_at    DATETIME     NOT NULL
    ) ENGINE=InnoDB
    """,
    # Companies the pharmacy buys medicines from.
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id    INT AUTO_INCREMENT PRIMARY KEY,
        name           VARCHAR(100) NOT NULL,
        contact_person VARCHAR(100),
        phone          VARCHAR(30),
        email          VARCHAR(100),
        address        VARCHAR(255)
    ) ENGINE=InnoDB
    """,
    # Individual medicine batches in stock. quantity/cost_price/sale_price/
    # expiry_date drive validation, low-stock and expiry highlighting, and the
    # profit-and-loss calculation. Each batch belongs to exactly one supplier.
    """
    CREATE TABLE IF NOT EXISTS medicines (
        medicine_id   INT AUTO_INCREMENT PRIMARY KEY,
        name          VARCHAR(120) NOT NULL,
        supplier_id   INT,
        batch_no      VARCHAR(50),
        quantity      INT          NOT NULL DEFAULT 0,
        reorder_level INT          NOT NULL DEFAULT 20,
        cost_price    DECIMAL(10,2) NOT NULL DEFAULT 0,
        sale_price    DECIMAL(10,2) NOT NULL DEFAULT 0,
        expiry_date   DATE,
        created_at    DATETIME     NOT NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            ON DELETE SET NULL
    ) ENGINE=InnoDB
    """,
    # Clinics the pharmacy wholesales to and tracks receivables for.
    """
    CREATE TABLE IF NOT EXISTS clinics (
        clinic_id      INT AUTO_INCREMENT PRIMARY KEY,
        name           VARCHAR(120) NOT NULL,
        contact_person VARCHAR(100),
        phone          VARCHAR(30),
        email          VARCHAR(100),
        address        VARCHAR(255)
    ) ENGINE=InnoDB
    """,
    # The ledger that answers "what does each clinic still owe me?" A 'charge'
    # row is medicine supplied on credit (increases the balance); a 'payment'
    # row is money received (decreases it). is_paid flags an individual charge
    # as settled so the UI can show paid / not-paid status per line.
    """
    CREATE TABLE IF NOT EXISTS clinic_transactions (
        txn_id      INT AUTO_INCREMENT PRIMARY KEY,
        clinic_id   INT NOT NULL,
        txn_date    DATE NOT NULL,
        description VARCHAR(255),
        amount      DECIMAL(10,2) NOT NULL,
        txn_type    ENUM('charge','payment') NOT NULL DEFAULT 'charge',
        is_paid     TINYINT(1) NOT NULL DEFAULT 0,
        FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id)
            ON DELETE CASCADE
    ) ENGINE=InnoDB
    """,
    # Every sale, used for profit/loss reports and the sales charts. unit_cost
    # is captured at sale time so profit stays correct even if prices change
    # later. clinic_id is NULL for an over-the-counter retail sale.
    """
    CREATE TABLE IF NOT EXISTS sales (
        sale_id     INT AUTO_INCREMENT PRIMARY KEY,
        sale_date   DATE NOT NULL,
        medicine_id INT,
        clinic_id   INT,
        quantity    INT NOT NULL,
        unit_price  DECIMAL(10,2) NOT NULL,
        unit_cost   DECIMAL(10,2) NOT NULL,
        total       DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id)
            ON DELETE SET NULL,
        FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id)
            ON DELETE SET NULL
    ) ENGINE=InnoDB
    """,
]


def init_schema(db):
    """Create every table if it does not already exist (safe to call on every
    launch). Returns nothing; raises if MySQL rejects a statement."""
    for statement in SCHEMA_STATEMENTS:
        db.execute(statement)


def is_seeded(db):
    """Return True if the database already has demo/real data, so we never
    double-seed on subsequent launches."""
    row = db.fetch_one("SELECT COUNT(*) AS n FROM users")
    return bool(row and row["n"] > 0)


def seed_demo_data(db):
    """Populate the empty database with a default login plus realistic
    suppliers, medicines, clinics, receivables and sales so the client can see
    the system working straight away. Only runs when the database is empty."""
    if is_seeded(db):
        return

    # --- Default staff account -------------------------------------------------
    # A single administrator the client can log in with on first run.
    pw_hash, salt = auth.hash_password("admin123")
    db.execute(
        "INSERT INTO users (username, password_hash, salt, full_name, role, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        ("admin", pw_hash, salt, "Arjun Mehta", "owner", datetime.datetime.now()),
    )

    # --- Suppliers -------------------------------------------------------------
    suppliers = [
        ("Cipla Distributors", "R. Nair", "022-555-0101", "sales@cipla-dist.example", "Andheri, Mumbai"),
        ("Sun Pharma Wholesale", "P. Joshi", "022-555-0144", "orders@sunwhole.example", "Vapi, Gujarat"),
        ("MediCore Agencies", "S. Khan", "022-555-0190", "contact@medicore.example", "Pune, Maharashtra"),
    ]
    db.executemany(
        "INSERT INTO suppliers (name, contact_person, phone, email, address) "
        "VALUES (%s,%s,%s,%s,%s)",
        suppliers,
    )

    # --- Medicines (mix of healthy, low-stock and soon-to-expire batches) ------
    today = datetime.date.today()

    def d(days):
        # Helper: a date "days" from today, written compactly for the seed rows.
        return today + datetime.timedelta(days=days)

    medicines = [
        # (name, supplier_id, batch, qty, reorder, cost, sale, expiry)
        ("Paracetamol 500mg", 1, "PCM-2401", 240, 50, 0.40, 1.20, d(400)),
        ("Amoxicillin 250mg", 1, "AMX-2402", 18, 40, 1.10, 3.00, d(20)),   # low stock + expiring soon
        ("Cetirizine 10mg", 2, "CTZ-2403", 130, 30, 0.25, 1.00, d(180)),
        ("Ibuprofen 400mg", 2, "IBU-2404", 75, 40, 0.50, 1.50, d(15)),     # expiring soon
        ("Metformin 500mg", 3, "MET-2405", 300, 60, 0.60, 1.80, d(500)),
        ("Azithromycin 500mg", 3, "AZI-2406", 12, 25, 2.20, 6.00, d(90)),  # low stock
        ("Cough Syrup 100ml", 1, "CSY-2407", 60, 20, 1.50, 4.00, d(8)),    # expiring very soon
        ("Vitamin C 1000mg", 2, "VTC-2408", 200, 40, 0.30, 1.10, d(700)),
    ]
    db.executemany(
        "INSERT INTO medicines "
        "(name, supplier_id, batch_no, quantity, reorder_level, cost_price, sale_price, expiry_date, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        [m + (datetime.datetime.now(),) for m in medicines],
    )

    # --- Clinics ---------------------------------------------------------------
    clinics = [
        ("Sunrise Family Clinic", "Dr. Rao", "022-555-0220", "front@sunrise.example", "Bandra, Mumbai"),
        ("Lotus Medical Centre", "Dr. Pillai", "022-555-0233", "admin@lotusmed.example", "Thane"),
        ("CarePoint Clinic", "Dr. Shah", "022-555-0277", "info@carepoint.example", "Dadar, Mumbai"),
    ]
    db.executemany(
        "INSERT INTO clinics (name, contact_person, phone, email, address) "
        "VALUES (%s,%s,%s,%s,%s)",
        clinics,
    )

    # --- Clinic receivables ledger --------------------------------------------
    # Charges (sold on credit) and payments. The running balance per clinic is
    # charges minus payments, which the reports turn into "amount owed".
    txns = [
        # (clinic_id, date, description, amount, type, is_paid)
        (1, d(-40), "Bulk antibiotics order", 4200.00, "charge", 1),
        (1, d(-35), "Part payment received", 2000.00, "payment", 1),
        (1, d(-10), "Monthly supply", 3100.00, "charge", 0),
        (2, d(-25), "Vitamins and syrups", 1800.00, "charge", 0),
        (2, d(-20), "Payment received", 1800.00, "payment", 1),
        (2, d(-5),  "Emergency stock", 2600.00, "charge", 0),
        (3, d(-15), "Opening supply", 950.00, "charge", 1),
        (3, d(-12), "Payment received", 950.00, "payment", 1),
        (3, d(-3),  "Restock order", 1450.00, "charge", 0),
    ]
    db.executemany(
        "INSERT INTO clinic_transactions "
        "(clinic_id, txn_date, description, amount, txn_type, is_paid) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        txns,
    )

    # --- Sales history (spread over the last ~60 days for the P&L report) ------
    sales = [
        # (date, medicine_id, clinic_id, qty, unit_price, unit_cost)
        (d(-55), 1, None, 30, 1.20, 0.40),
        (d(-50), 3, 1, 40, 1.00, 0.25),
        (d(-45), 5, None, 25, 1.80, 0.60),
        (d(-40), 2, 1, 20, 3.00, 1.10),
        (d(-33), 4, None, 15, 1.50, 0.50),
        (d(-28), 6, 2, 10, 6.00, 2.20),
        (d(-21), 8, None, 50, 1.10, 0.30),
        (d(-18), 1, 3, 60, 1.20, 0.40),
        (d(-12), 5, None, 40, 1.80, 0.60),
        (d(-7),  3, 2, 35, 1.00, 0.25),
        (d(-4),  7, None, 20, 4.00, 1.50),
        (d(-1),  2, None, 12, 3.00, 1.10),
    ]
    db.executemany(
        "INSERT INTO sales "
        "(sale_date, medicine_id, clinic_id, quantity, unit_price, unit_cost, total) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        [(s[0], s[1], s[2], s[3], s[4], s[5], round(s[3] * s[4], 2)) for s in sales],
    )


def bootstrap():
    """Convenience used by run.py: open a connection, ensure the schema exists,
    seed demo data on first run, and hand back the ready-to-use Database."""
    db = Database()
    init_schema(db)
    seed_demo_data(db)
    return db
