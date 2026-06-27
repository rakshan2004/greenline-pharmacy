"""Entry point for the Greenline Pharmacy application.

Run this file to start the program:  python3 run.py

It performs three steps in order:
  1. Connects to MySQL, creates the tables if they are missing and seeds demo
     data on the very first run (database.bootstrap()).
  2. Builds the main window (which begins at the login screen).
  3. Hands control to Tkinter's event loop so the GUI becomes interactive.

A clear error is printed if MySQL is not running, pointing the user at the
helper script that starts the local database server.
"""

import sys

import mysql.connector

from greenline import database
from greenline.ui.main_window import MainWindow


def main():
    # Step 1: open the database and make sure it is ready to use. If the server
    # is not running the connector raises, so we catch it and explain how to
    # start the bundled local MySQL instance instead of dumping a raw traceback.
    try:
        db = database.bootstrap()
    except mysql.connector.Error as exc:
        print("Could not connect to the Greenline database.")
        print("Start the local MySQL server first with:  ./start_db.sh")
        print("Underlying error:", exc)
        sys.exit(1)

    # Step 2 and 3: build the window and run the GUI event loop until the user
    # closes it, then tidy up the database connection.
    app = MainWindow(db)
    app.mainloop()
    db.close()


if __name__ == "__main__":
    main()
