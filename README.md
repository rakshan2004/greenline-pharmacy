# Greenline Pharmacy

A desktop management system for Mr. Arjun Mehta's Greenline Pharmacy, built to
the Criteria A planning document. It replaces his notebook-and-Excel workflow
with a single WIMP (windows / icons / menus / pointer) application: staff log
in, manage medicine stock and suppliers, track what each clinic owes on credit,
and read reports and charts instead of adding things up by hand.

Built with **Python 3 + Tkinter** (front end) and a **MySQL** relational
database (back end), all using freeware so there is no software cost.

## How to run

```bash
# 1. Start the bundled, project-local MySQL server (first run initialises it).
./start_db.sh

# 2. Launch the application.
python3 run.py
```

Default login on first run: **username `admin`, password `admin123`**. The
database is created and filled with realistic demo data automatically the first
time you run it.

### Requirements
- Python 3 with the `tkinter` module (bundled with python.org installers).
- `pip install mysql-connector-python matplotlib`
- A `mysqld`/`mysql` binary (the start script points at the local anaconda one).

## Project structure

```
run.py                     Entry point: opens the DB, builds the window, runs the GUI.
start_db.sh                Starts the project-private MySQL server on port 3309.
greenline/
  config.py                Database credentials, app name, business-rule constants.
  database.py              Connection wrapper + schema (CREATE TABLE) + demo seed data.
  auth.py                  Salted PBKDF2 password hashing and login checks.
  theme.py                 The custom "Greenline" look: palette, fonts, styled widgets.
  ui/
    main_window.py         The shell: login gate + sidebar navigation between screens.
    login_view.py          Username/password login with validation.
    dashboard_view.py      Overview cards + expiring-soon and low-stock alerts.
    medicines_view.py      Medicine/supplier CRUD, search, expiry/low-stock highlighting.
    clinics_view.py        Clinic accounts and the credit / paid-unpaid ledger.
    reports_view.py        Receivables, profit & loss by date range, stock by supplier.
    charts_view.py         Pie and bar charts (matplotlib embedded in Tkinter).
```

## How the build meets the Criteria A success criteria

| Success criterion (Appendix 1) | Where it lives |
| --- | --- |
| Log in with username/password, with validation; passwords protected (pt 7) | `login_view.py` + `auth.py` (PBKDF2 + per-user salt; no plain-text storage) |
| Create / edit / remove medicines from all suppliers | `medicines_view.py` (add/edit/delete dialogs, supplier manager) |
| Add / edit / delete clinic accounts incl. credit and paid / not-paid (pt 8) | `clinics_view.py` (clinic CRUD + charge/payment ledger + paid toggle) |
| Report of what each clinic still owes (pt 8) | `reports_view.py` "Receivables by clinic"; also on the dashboard |
| Profit & loss report for a selected date range | `reports_view.py` "Profit & Loss" |
| Validation on entry (no negative stock, no blank mandatory fields) | every input dialog validates before saving |
| Drugs near expiry automatically highlighted (pt 9) | `dashboard_view.py` alerts + amber/red rows in `medicines_view.py` |
| Report of total current stock by supplier | `reports_view.py` "Stock by supplier" |
| Search stock by supplier, medicine, or expiry date | `medicines_view.py` toolbar search |
| Sales and stock shown as pie / bar charts | `charts_view.py` |
| Relational database (linked records, no redundant copying) | `database.py` schema with foreign keys |

## Notes
- The MySQL data directory lives in `.mysql_data/` inside the project and runs
  on port 3309, so it never interferes with any other MySQL on the machine.
- Money is shown in rupees (`Rs`) to match the client's retail context.
```
