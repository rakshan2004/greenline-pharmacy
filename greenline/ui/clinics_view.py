"""The clinics & receivables screen: where medical reps manage the clinics the
pharmacy supplies on credit and keep track of what each one still owes.

This is a master/detail screen (Criteria A: "add, edit and delete clinic
accounts including credit and paid / not-paid details" and "how will I know
what each clinic still owes me?"). The left half lists every clinic with its
running balance; selecting a clinic fills the right half with its contact
details, a headline "balance owed" figure and a full ledger of its charges and
payments.

The balance for a clinic is charges minus payments (see the schema note on
clinic_transactions): a 'charge' is medicine supplied on credit and increases
what they owe, a 'payment' is money received and decreases it. The is_paid flag
marks an individual charge line as settled so each row can show paid / not-paid.

As with the other views all data is loaded in refresh() rather than __init__ so
the figures are always re-queried when the screen is shown.
"""

import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from greenline import theme


class ClinicsView(tk.Frame):
    """The clinics master/detail screen. The static frame (header, the two
    panels and their tables/buttons) is built once in __init__; refresh()
    reloads the clinic list and re-paints the detail panel from the database."""

    def __init__(self, parent, db):
        super().__init__(parent, bg=theme.color("bg"))
        self.db = db
        self._selected_clinic_id = None     # id of the clinic shown on the right

        # Outer padding so content does not touch the window edges (matches the
        # other views).
        outer = theme.frame(self, bg="bg")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        # --- Page header (static) ---------------------------------------------
        header = theme.frame(outer, bg="bg")
        header.pack(fill="x", anchor="w")
        theme.heading(header, "Clinics & Credit", bg="bg").pack(anchor="w")
        theme.label(
            header,
            "Manage clinic accounts and track what each one still owes.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(2, 0))

        # --- Body: master (left) and detail (right) side by side --------------
        body = theme.frame(outer, bg="bg")
        body.pack(fill="both", expand=True, pady=(20, 0))

        self._build_master(body)
        self._build_detail(body)

    # ------------------------------------------------------------------ helpers
    def _money(self, value):
        """Format a numeric amount as a rupee string with thousands separators.
        DECIMAL columns arrive as Python Decimal, so wrap in float() first; a
        missing/NULL aggregate (None) is treated as zero."""
        return "Rs {:,.2f}".format(float(value or 0))

    # -------------------------------------------------------------- master pane
    def _build_master(self, parent):
        """Build the left-hand panel: the clinic list table and the add / edit /
        delete buttons beneath it."""
        # A fixed-width column on the left so the detail panel takes the rest.
        left = theme.card(parent)
        left.pack(side="left", fill="y", padx=(0, 12))
        inner = theme.frame(left, bg="surface")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        theme.label(inner, "Clinics", kind="heading", fg="text",
                    bg="surface").pack(anchor="w", pady=(0, 10))

        # Two-column table: clinic name and its current balance owed.
        self.clinic_tree = ttk.Treeview(
            inner, columns=("name", "owed"), show="headings",
            style="Greenline.Treeview", height=16, selectmode="browse",
        )
        self.clinic_tree.heading("name", text="Name")
        self.clinic_tree.heading("owed", text="Owed")
        self.clinic_tree.column("name", width=190, anchor="w")
        self.clinic_tree.column("owed", width=110, anchor="e")
        self.clinic_tree.pack(fill="both", expand=True)

        # Row tints: amber when the clinic owes money, brand green when settled.
        self.clinic_tree.tag_configure("owing", foreground=theme.color("amber"))
        self.clinic_tree.tag_configure("clear", foreground=theme.color("primary"))

        # Re-draw the detail panel whenever the highlighted clinic changes.
        self.clinic_tree.bind("<<TreeviewSelect>>", self._on_clinic_selected)

        # Action buttons for the clinic records themselves.
        buttons = theme.frame(inner, bg="surface")
        buttons.pack(fill="x", pady=(12, 0))
        theme.button(buttons, "Add clinic", command=self._add_clinic,
                     kind="primary").pack(side="left")
        theme.button(buttons, "Edit clinic", command=self._edit_clinic,
                     kind="ghost").pack(side="left", padx=6)
        theme.button(buttons, "Delete clinic", command=self._delete_clinic,
                     kind="danger").pack(side="left")

    # -------------------------------------------------------------- detail pane
    def _build_detail(self, parent):
        """Build the right-hand panel: the selected clinic's name, contact info,
        headline balance, its transaction ledger and the ledger action buttons.
        The text labels are created here once and updated in refresh()."""
        right = theme.card(parent)
        right.pack(side="left", fill="both", expand=True)
        inner = theme.frame(right, bg="surface")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        # Clinic name heading (blank until a clinic is selected).
        self.detail_name = theme.label(inner, "", kind="heading", fg="text",
                                       bg="surface")
        self.detail_name.pack(anchor="w")

        # Contact details on one muted line below the name.
        self.detail_contact = theme.label(inner, "", kind="small", fg="muted",
                                          bg="surface", justify="left")
        self.detail_contact.pack(anchor="w", pady=(2, 0))

        # Big headline balance: amber when they owe money, green when clear.
        self.detail_balance = theme.label(inner, "", kind="title", fg="primary",
                                          bg="surface")
        self.detail_balance.pack(anchor="w", pady=(12, 12))

        # Ledger table of this clinic's charges and payments.
        self.ledger_tree = ttk.Treeview(
            inner, columns=("date", "desc", "type", "amount", "status"),
            show="headings", style="Greenline.Treeview", selectmode="browse",
        )
        self.ledger_tree.heading("date", text="Date")
        self.ledger_tree.heading("desc", text="Description")
        self.ledger_tree.heading("type", text="Type")
        self.ledger_tree.heading("amount", text="Amount")
        self.ledger_tree.heading("status", text="Status")
        self.ledger_tree.column("date", width=100, anchor="w")
        self.ledger_tree.column("desc", width=240, anchor="w")
        self.ledger_tree.column("type", width=90, anchor="w")
        self.ledger_tree.column("amount", width=120, anchor="e")
        self.ledger_tree.column("status", width=90, anchor="center")
        self.ledger_tree.pack(fill="both", expand=True)

        # Tint unpaid charge rows amber so outstanding lines stand out.
        self.ledger_tree.tag_configure("unpaid",
                                       foreground=theme.color("amber"))

        # Ledger action buttons.
        ledger_buttons = theme.frame(inner, bg="surface")
        ledger_buttons.pack(fill="x", pady=(12, 0))
        theme.button(ledger_buttons, "Add charge", command=self._add_charge,
                     kind="primary").pack(side="left")
        theme.button(ledger_buttons, "Add payment", command=self._add_payment,
                     kind="ghost").pack(side="left", padx=6)
        theme.button(ledger_buttons, "Toggle paid/unpaid",
                     command=self._toggle_paid, kind="ghost").pack(side="left")
        theme.button(ledger_buttons, "Delete entry", command=self._delete_entry,
                     kind="danger").pack(side="left", padx=6)

    # ------------------------------------------------------------------ refresh
    def refresh(self):
        """Reload the clinic list and re-paint the detail panel. Called by the
        navigation shell every time this screen is shown."""
        self._load_clinics()
        self._load_detail()

    def _load_clinics(self):
        """Re-query every clinic together with its running balance and rebuild
        the master table, restoring the previous selection where possible."""
        # Wipe the existing rows before reloading.
        for item in self.clinic_tree.get_children():
            self.clinic_tree.delete(item)

        # One query joins each clinic to its ledger and reduces it to a single
        # balance (charges add, payments subtract). LEFT JOIN keeps clinics with
        # no transactions; COALESCE turns their NULL balance into 0.
        rows = self.db.fetch_all(
            "SELECT c.clinic_id, c.name, "
            "COALESCE(SUM(CASE WHEN t.txn_type='charge' THEN t.amount "
            "ELSE -t.amount END), 0) AS owed "
            "FROM clinics c "
            "LEFT JOIN clinic_transactions t ON t.clinic_id = c.clinic_id "
            "GROUP BY c.clinic_id, c.name "
            "ORDER BY c.name ASC"
        )

        for row in rows:
            owed = float(row["owed"] or 0)
            # A positive balance means money is still owed (amber); zero or a
            # credit balance is treated as settled (green).
            tag = "owing" if owed > 0 else "clear"
            self.clinic_tree.insert(
                "", "end", iid=str(row["clinic_id"]),
                values=(row["name"], self._money(owed)), tags=(tag,),
            )

        # Re-select the previously selected clinic if it still exists, otherwise
        # fall back to the first row so the detail panel is never left stale.
        if self._selected_clinic_id is not None and \
                self.clinic_tree.exists(str(self._selected_clinic_id)):
            self.clinic_tree.selection_set(str(self._selected_clinic_id))
        elif rows:
            first_id = rows[0]["clinic_id"]
            self._selected_clinic_id = first_id
            self.clinic_tree.selection_set(str(first_id))
        else:
            self._selected_clinic_id = None

    def _on_clinic_selected(self, _event=None):
        """<<TreeviewSelect>> handler: remember the chosen clinic and refresh the
        detail panel to match."""
        selection = self.clinic_tree.selection()
        if not selection:
            return
        self._selected_clinic_id = int(selection[0])
        self._load_detail()

    def _load_detail(self):
        """Re-paint the right-hand panel for the currently selected clinic: its
        name, contacts, headline balance and full ledger."""
        # Clear any rows already in the ledger table.
        for item in self.ledger_tree.get_children():
            self.ledger_tree.delete(item)

        # Nothing selected (e.g. no clinics exist yet): blank the panel.
        if self._selected_clinic_id is None:
            self.detail_name.config(text="No clinic selected")
            self.detail_contact.config(text="")
            self.detail_balance.config(text="")
            return

        clinic = self.db.fetch_one(
            "SELECT clinic_id, name, contact_person, phone, email, address "
            "FROM clinics WHERE clinic_id = %s",
            (self._selected_clinic_id,),
        )
        # The clinic may have been deleted on another screen; bail gracefully.
        if clinic is None:
            self._selected_clinic_id = None
            self.detail_name.config(text="No clinic selected")
            self.detail_contact.config(text="")
            self.detail_balance.config(text="")
            return

        self.detail_name.config(text=clinic["name"])

        # Assemble the contact line from whichever fields are filled in.
        parts = []
        if clinic["contact_person"]:
            parts.append(clinic["contact_person"])
        if clinic["phone"]:
            parts.append(clinic["phone"])
        if clinic["email"]:
            parts.append(clinic["email"])
        if clinic["address"]:
            parts.append(clinic["address"])
        self.detail_contact.config(
            text="   |   ".join(parts) if parts else "No contact details on file"
        )

        # Headline balance for this clinic (charges minus payments).
        balance_row = self.db.fetch_one(
            "SELECT COALESCE(SUM(CASE WHEN txn_type='charge' THEN amount "
            "ELSE -amount END), 0) AS owed FROM clinic_transactions "
            "WHERE clinic_id = %s",
            (self._selected_clinic_id,),
        )
        owed = float(balance_row["owed"] or 0)
        # Amber if they still owe, brand green once clear.
        balance_fg = "amber" if owed > 0 else "primary"
        self.detail_balance.config(
            text="Balance owed: " + self._money(owed),
            fg=theme.color(balance_fg),
        )

        # The ledger itself, newest first.
        txns = self.db.fetch_all(
            "SELECT txn_id, txn_date, description, amount, txn_type, is_paid "
            "FROM clinic_transactions WHERE clinic_id = %s "
            "ORDER BY txn_date DESC, txn_id DESC",
            (self._selected_clinic_id,),
        )
        for txn in txns:
            # Status only applies to charges: a payment is shown as a dash.
            if txn["txn_type"] == "charge":
                status = "PAID" if txn["is_paid"] else "UNPAID"
            else:
                status = "-"
            # Tint unpaid charges amber to flag outstanding lines.
            tags = ("unpaid",) if (txn["txn_type"] == "charge"
                                   and not txn["is_paid"]) else ()
            self.ledger_tree.insert(
                "", "end", iid=str(txn["txn_id"]),
                values=(
                    txn["txn_date"].isoformat(),
                    txn["description"] or "",
                    txn["txn_type"].capitalize(),
                    self._money(txn["amount"]),
                    status,
                ),
                tags=tags,
            )

    # ------------------------------------------------------- selection helpers
    def _require_clinic(self):
        """Return the selected clinic id, or warn and return None if there is no
        clinic to act on. Used by every action that needs a target clinic."""
        if self._selected_clinic_id is None:
            messagebox.showwarning(
                "No clinic selected",
                "Please select a clinic first.",
                parent=self,
            )
            return None
        return self._selected_clinic_id

    def _selected_txn_id(self):
        """Return the highlighted ledger row's txn_id, or None if nothing in the
        ledger is selected."""
        selection = self.ledger_tree.selection()
        if not selection:
            return None
        return int(selection[0])

    # ------------------------------------------------------- clinic dialogs/CRUD
    def _add_clinic(self):
        """Open a blank clinic form; on save insert the new clinic."""
        self._clinic_dialog(existing=None)

    def _edit_clinic(self):
        """Open the clinic form pre-filled with the selected clinic's details."""
        clinic_id = self._require_clinic()
        if clinic_id is None:
            return
        clinic = self.db.fetch_one(
            "SELECT clinic_id, name, contact_person, phone, email, address "
            "FROM clinics WHERE clinic_id = %s",
            (clinic_id,),
        )
        if clinic is None:
            return
        self._clinic_dialog(existing=clinic)

    def _clinic_dialog(self, existing):
        """Shared add/edit form. "existing" is None for an add or a clinic dict
        for an edit. Name is mandatory; the other fields are optional."""
        is_edit = existing is not None
        win = tk.Toplevel(self)
        win.title("Edit clinic" if is_edit else "Add clinic")
        win.configure(bg=theme.color("bg"))
        win.transient(self.winfo_toplevel())   # keep it above the main window
        win.resizable(False, False)

        # A surface card holds the labelled fields, matching the form styling.
        card = theme.card(win)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        # Build a labelled entry per field and keep the widgets to read later.
        fields = [
            ("name", "Name (required)"),
            ("contact_person", "Contact person"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("address", "Address"),
        ]
        entries = {}
        for key, caption in fields:
            row, entry = theme.field_row(card, caption)
            row.pack(fill="x", pady=6)
            # Pre-fill the entry when editing an existing clinic.
            if is_edit and existing[key]:
                entry.insert(0, existing[key])
            entries[key] = entry

        def on_save():
            # Mandatory-field validation (Criteria A): name cannot be blank.
            name = entries["name"].get().strip()
            if not name:
                messagebox.showwarning(
                    "Missing name",
                    "A clinic name is required.",
                    parent=win,
                )
                return

            # Collect the optional fields, storing NULL where left blank.
            contact = entries["contact_person"].get().strip() or None
            phone = entries["phone"].get().strip() or None
            email = entries["email"].get().strip() or None
            address = entries["address"].get().strip() or None

            if is_edit:
                self.db.execute(
                    "UPDATE clinics SET name=%s, contact_person=%s, phone=%s, "
                    "email=%s, address=%s WHERE clinic_id=%s",
                    (name, contact, phone, email, address,
                     existing["clinic_id"]),
                )
            else:
                # Remember the new clinic so refresh() re-selects it.
                new_id = self.db.execute(
                    "INSERT INTO clinics "
                    "(name, contact_person, phone, email, address) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (name, contact, phone, email, address),
                )
                self._selected_clinic_id = new_id

            win.destroy()
            self.refresh()

        self._dialog_buttons(card, win, on_save)

    def _delete_clinic(self):
        """Delete the selected clinic after confirmation. The clinic_transactions
        foreign key cascades, so its ledger rows are removed by the database."""
        clinic_id = self._require_clinic()
        if clinic_id is None:
            return
        clinic = self.db.fetch_one(
            "SELECT name FROM clinics WHERE clinic_id = %s", (clinic_id,)
        )
        name = clinic["name"] if clinic else "this clinic"
        # Spell out the cascade so the user is not surprised by lost history.
        if not messagebox.askyesno(
            "Delete clinic",
            "Delete '{}' and all of its credit history?".format(name),
            parent=self,
        ):
            return
        self.db.execute("DELETE FROM clinics WHERE clinic_id = %s", (clinic_id,))
        # Clear the selection so refresh() falls back to the first clinic.
        self._selected_clinic_id = None
        self.refresh()

    # ----------------------------------------------------- transaction dialogs
    def _add_charge(self):
        """Open the transaction form to record medicine supplied on credit."""
        self._txn_dialog(txn_type="charge")

    def _add_payment(self):
        """Open the transaction form to record money received from the clinic."""
        self._txn_dialog(txn_type="payment")

    def _txn_dialog(self, txn_type):
        """Shared add-charge / add-payment form. Date must parse, amount must be
        a valid positive number (Criteria A validation). New charges start as
        not-paid; payments do not carry a paid flag."""
        clinic_id = self._require_clinic()
        if clinic_id is None:
            return

        is_charge = txn_type == "charge"
        win = tk.Toplevel(self)
        win.title("Add charge" if is_charge else "Add payment")
        win.configure(bg=theme.color("bg"))
        win.transient(self.winfo_toplevel())
        win.resizable(False, False)

        card = theme.card(win)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        # Date defaults to today; it is validated by strptime on save.
        date_row, date_entry = theme.field_row(card, "Date (YYYY-MM-DD)")
        date_row.pack(fill="x", pady=6)
        date_entry.insert(0, datetime.date.today().isoformat())

        desc_row, desc_entry = theme.field_row(card, "Description")
        desc_row.pack(fill="x", pady=6)

        amount_row, amount_entry = theme.field_row(card, "Amount (Rs)")
        amount_row.pack(fill="x", pady=6)

        def on_save():
            # Date validation: must parse as YYYY-MM-DD.
            date_text = date_entry.get().strip()
            try:
                txn_date = datetime.datetime.strptime(
                    date_text, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning(
                    "Invalid date",
                    "Please enter the date as YYYY-MM-DD.",
                    parent=win,
                )
                return

            # Amount validation: must be a number greater than zero.
            amount_text = amount_entry.get().strip()
            try:
                amount = float(amount_text)
            except ValueError:
                messagebox.showwarning(
                    "Invalid amount",
                    "Please enter the amount as a number.",
                    parent=win,
                )
                return
            if amount <= 0:
                messagebox.showwarning(
                    "Invalid amount",
                    "The amount must be greater than zero.",
                    parent=win,
                )
                return

            description = desc_entry.get().strip() or None
            # New charges default to not-paid (is_paid=0); payments store 0 too
            # as the flag only has meaning for charges.
            self.db.execute(
                "INSERT INTO clinic_transactions "
                "(clinic_id, txn_date, description, amount, txn_type, is_paid) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (clinic_id, txn_date, description, amount, txn_type, 0),
            )
            win.destroy()
            self.refresh()

        self._dialog_buttons(card, win, on_save)

    def _toggle_paid(self):
        """Flip the is_paid flag on the selected charge. Only charges carry a
        paid status, so a payment selection is rejected with a warning."""
        if self._require_clinic() is None:
            return
        txn_id = self._selected_txn_id()
        if txn_id is None:
            messagebox.showwarning(
                "No entry selected",
                "Please select a charge in the ledger first.",
                parent=self,
            )
            return

        txn = self.db.fetch_one(
            "SELECT txn_type, is_paid FROM clinic_transactions "
            "WHERE txn_id = %s",
            (txn_id,),
        )
        if txn is None:
            return
        # Paid / not-paid only makes sense for charges.
        if txn["txn_type"] != "charge":
            messagebox.showwarning(
                "Not a charge",
                "Only charges can be marked paid or unpaid.",
                parent=self,
            )
            return

        # Flip the flag (1 -> 0, 0 -> 1).
        new_flag = 0 if txn["is_paid"] else 1
        self.db.execute(
            "UPDATE clinic_transactions SET is_paid = %s WHERE txn_id = %s",
            (new_flag, txn_id),
        )
        self.refresh()

    def _delete_entry(self):
        """Delete the selected ledger entry after confirmation."""
        if self._require_clinic() is None:
            return
        txn_id = self._selected_txn_id()
        if txn_id is None:
            messagebox.showwarning(
                "No entry selected",
                "Please select a ledger entry first.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Delete entry",
            "Delete this ledger entry?",
            parent=self,
        ):
            return
        self.db.execute(
            "DELETE FROM clinic_transactions WHERE txn_id = %s", (txn_id,)
        )
        self.refresh()

    # ------------------------------------------------------------- dialog chrome
    def _dialog_buttons(self, parent, win, on_save):
        """Add a shared Save / Cancel button row to a dialog. Save runs the
        supplied callback; Cancel simply closes the window."""
        buttons = theme.frame(parent, bg="surface")
        buttons.pack(fill="x", pady=(14, 0))
        theme.button(buttons, "Save", command=on_save,
                     kind="primary").pack(side="left")
        theme.button(buttons, "Cancel", command=win.destroy,
                     kind="ghost").pack(side="left", padx=6)
