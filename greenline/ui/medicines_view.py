"""The medicines and stock management screen: the heart of the inventory system.

This is where the client creates, edits and removes the medicine batches that
every other part of the program depends on (Criteria A, Appendix 1). It presents
the whole stock list in one table, automatically tints rows that are expired,
nearing expiry or running low so problems jump out without any reading, and lets
the client search the list by medicine name, supplier or expiry date. Add and
edit happen in small pop-up forms that validate every field (no blank names, no
negative quantities, properly formatted dates) before anything touches the
database. A second pop-up manages the suppliers a medicine must belong to.

As with the other views, all live data is loaded in refresh() rather than
__init__ so the table is always re-queried when the screen is shown and reflects
edits made elsewhere.
"""

import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from greenline import config
from greenline import theme


# Subtle dark tints used to highlight problem rows. They are deliberately dark
# so the theme's light text stays readable on top of them (a plain bright red
# row would wash the text out).
TINT_EXPIRED  = "#3A1414"   # already past its expiry date (most urgent)
TINT_EXPIRING = "#3A2E12"   # within the expiry-warning window
TINT_LOW      = "#163049"   # stock at or below the reorder level


class MedicinesView(tk.Frame):
    """The stock list screen. The static layout (toolbar, table, legend) is
    built once in __init__; refresh() simply re-runs the query and repopulates
    the table, applying the highlight tags as it goes."""

    def __init__(self, parent, db):
        super().__init__(parent, bg=theme.color("bg"))
        self.db = db

        # The current search filter. Empty string means "show everything"; it is
        # remembered so refresh() (called after an add/edit/delete) keeps the
        # user's search applied instead of silently resetting the list.
        self._search_field = "Medicine"
        self._search_term = ""

        # Outer padding so the content does not touch the window edges.
        outer = theme.frame(self, bg="bg")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        # --- Page header (static) ---------------------------------------------
        header = theme.frame(outer, bg="bg")
        header.pack(fill="x", anchor="w")
        theme.heading(header, "Medicines & stock", bg="bg").pack(anchor="w")
        theme.label(
            header,
            "Add, edit and search your medicine batches. Rows are highlighted "
            "automatically when stock is expired, expiring or running low.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(2, 0))

        # --- Toolbar (search + action buttons) --------------------------------
        self._build_toolbar(outer)

        # --- Stock table ------------------------------------------------------
        self._build_table(outer)

        # --- Colour legend ----------------------------------------------------
        self._build_legend(outer)

    # ------------------------------------------------------------------ toolbar
    def _build_toolbar(self, parent):
        """Build the search box, the 'search by' dropdown and the action
        buttons. Laid out on one row above the table."""
        bar = theme.frame(parent, bg="bg")
        bar.pack(fill="x", pady=(18, 10))

        # Search controls on the left.
        theme.label(bar, "Search", kind="small", fg="muted",
                    bg="bg").pack(side="left", padx=(0, 6))
        self.search_entry = theme.entry(bar, width=22)
        self.search_entry.pack(side="left")
        # Return in the box triggers the same search as the button.
        self.search_entry.bind("<Return>", lambda _e: self._do_search())

        # The "search by" dropdown decides which column the term is matched on.
        self.search_by = theme.combobox(
            bar, ["Medicine", "Supplier", "Expiry before"], width=14
        )
        self.search_by.current(0)
        self.search_by.pack(side="left", padx=6)

        theme.button(bar, "Search", command=self._do_search,
                     kind="primary").pack(side="left", padx=(2, 0))
        theme.button(bar, "Clear", command=self._clear_search,
                     kind="ghost").pack(side="left", padx=6)

        # Action buttons on the right, in order of frequency of use.
        theme.button(bar, "Manage suppliers", command=self._open_suppliers,
                     kind="ghost").pack(side="right")
        theme.button(bar, "Delete selected", command=self._delete_selected,
                     kind="danger").pack(side="right", padx=6)
        theme.button(bar, "Edit selected", command=self._edit_selected,
                     kind="ghost").pack(side="right")
        theme.button(bar, "Add medicine", command=self._add_medicine,
                     kind="primary").pack(side="right", padx=6)

    # -------------------------------------------------------------------- table
    def _build_table(self, parent):
        """Create the Treeview that lists every medicine batch, with numeric
        columns right-aligned and the highlight tags pre-configured."""
        # The card gives the table a bordered panel to sit in.
        card = theme.card(parent)
        card.pack(fill="both", expand=True)
        inner = theme.frame(card, bg="surface")
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # Column identifiers paired with their display headings.
        self.columns = (
            "name", "supplier", "batch", "qty",
            "reorder", "cost", "sale", "expiry",
        )
        headings = {
            "name": "Name", "supplier": "Supplier", "batch": "Batch",
            "qty": "Qty", "reorder": "Reorder", "cost": "Cost",
            "sale": "Sale", "expiry": "Expiry",
        }
        # Numeric columns are right-aligned so figures line up by place value.
        right_aligned = {"qty", "reorder", "cost", "sale"}

        self.tree = ttk.Treeview(
            inner, columns=self.columns, show="headings",
            style="Greenline.Treeview", height=14,
        )
        for col in self.columns:
            anchor = "e" if col in right_aligned else "w"
            self.tree.heading(col, text=headings[col], anchor=anchor)
            # Wider columns for the free-text fields, narrow for the numbers.
            width = 90
            if col in ("name", "supplier"):
                width = 180
            elif col in ("batch", "expiry"):
                width = 110
            self.tree.column(col, width=width, anchor=anchor, stretch=True)

        # A vertical scrollbar for long stock lists.
        scroll = ttk.Scrollbar(inner, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # Double-clicking a row is a natural shortcut for "edit".
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        # Pre-configure the row highlight tags using the dark problem tints.
        self.tree.tag_configure("expired", background=TINT_EXPIRED,
                                foreground=theme.color("text"))
        self.tree.tag_configure("expiring", background=TINT_EXPIRING,
                                foreground=theme.color("text"))
        self.tree.tag_configure("low", background=TINT_LOW,
                                foreground=theme.color("text"))

    # ------------------------------------------------------------------- legend
    def _build_legend(self, parent):
        """A small key explaining what each highlight colour means, so the
        client never has to guess why a row is tinted."""
        legend = theme.frame(parent, bg="bg")
        legend.pack(fill="x", pady=(10, 0))

        # (caption, swatch colour) pairs matching the row tags above.
        items = [
            ("Expired", TINT_EXPIRED),
            ("Expiring within {} days".format(config.EXPIRY_WARNING_DAYS),
             TINT_EXPIRING),
            ("Low stock (at or below reorder level)", TINT_LOW),
        ]
        for caption, swatch in items:
            chip = theme.frame(legend, bg="bg")
            chip.pack(side="left", padx=(0, 18))
            # A small coloured square followed by the explanatory text.
            box = tk.Frame(chip, bg=swatch, width=14, height=14,
                           highlightbackground=theme.color("border"),
                           highlightthickness=1)
            box.pack(side="left", padx=(0, 6))
            box.pack_propagate(False)
            theme.label(chip, caption, kind="small", fg="muted",
                        bg="bg").pack(side="left")

    # -------------------------------------------------------------------- helpers
    def _money(self, value):
        """Format a DECIMAL column as a plain two-decimal string. DECIMAL values
        arrive as Python Decimal, so wrap in float() first."""
        return "{:.2f}".format(float(value or 0))

    def _load_suppliers(self):
        """Return the supplier rows ordered by name. Shared by the search-free
        refresh and by the add/edit form's supplier dropdown."""
        return self.db.fetch_all(
            "SELECT supplier_id, name FROM suppliers ORDER BY name ASC"
        )

    # ------------------------------------------------------------------- search
    def _do_search(self):
        """Remember the current search box contents and dropdown choice, then
        rebuild the table so only matching rows show."""
        self._search_field = self.search_by.get()
        self._search_term = self.search_entry.get().strip()
        self.refresh()

    def _clear_search(self):
        """Reset the search box and dropdown and show the full list again."""
        self.search_entry.delete(0, "end")
        self.search_by.current(0)
        self._search_field = "Medicine"
        self._search_term = ""
        self.refresh()

    def _build_query(self):
        """Translate the remembered search filter into a SQL WHERE clause and
        parameters. Returns (sql, params). The supplier name is always joined in
        (LEFT JOIN so medicines with no supplier still appear)."""
        sql = (
            "SELECT m.medicine_id, m.name, m.batch_no, m.quantity, "
            "m.reorder_level, m.cost_price, m.sale_price, m.expiry_date, "
            "m.supplier_id, s.name AS supplier_name "
            "FROM medicines m "
            "LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id"
        )
        params = []
        term = self._search_term

        if term:
            if self._search_field == "Supplier":
                # Match against the supplier's name.
                sql += " WHERE s.name LIKE %s"
                params.append("%" + term + "%")
            elif self._search_field == "Expiry before":
                # Treat the term as a YYYY-MM-DD cut-off; bad dates are ignored
                # so the search simply shows everything rather than erroring.
                try:
                    cutoff = datetime.datetime.strptime(term, "%Y-%m-%d").date()
                    sql += " WHERE m.expiry_date IS NOT NULL AND m.expiry_date <= %s"
                    params.append(cutoff)
                except ValueError:
                    messagebox.showerror(
                        "Invalid date",
                        "Enter the expiry cut-off as YYYY-MM-DD (for example "
                        "2026-12-31).",
                    )
            else:
                # Default: match against the medicine name.
                sql += " WHERE m.name LIKE %s"
                params.append("%" + term + "%")

        sql += " ORDER BY m.name ASC"
        return sql, tuple(params)

    # ------------------------------------------------------------------ refresh
    def refresh(self):
        """Re-query the medicines (honouring any active search) and repopulate
        the table, tagging each row with its expiry/low-stock highlight. Called
        by the navigation shell every time the screen is shown."""
        # Wipe the existing rows before reloading.
        for item in self.tree.get_children():
            self.tree.delete(item)

        today = datetime.date.today()
        warn_cutoff = today + datetime.timedelta(days=config.EXPIRY_WARNING_DAYS)

        sql, params = self._build_query()
        rows = self.db.fetch_all(sql, params)

        for row in rows:
            expiry = row["expiry_date"]
            supplier = row["supplier_name"] or "-"

            # Decide the highlight tag with a clear precedence: an expired batch
            # is more urgent than a merely expiring one, which is more urgent
            # than low stock. Only one tag is applied so the colour is unambiguous.
            tags = ()
            if expiry is not None and expiry < today:
                tags = ("expired",)
            elif expiry is not None and expiry <= warn_cutoff:
                tags = ("expiring",)
            elif row["quantity"] <= row["reorder_level"]:
                tags = ("low",)

            # The Treeview stores the medicine_id as the item id (iid) so edit
            # and delete can look the record back up without a separate column.
            self.tree.insert(
                "", "end", iid=str(row["medicine_id"]),
                values=(
                    row["name"],
                    supplier,
                    row["batch_no"] or "-",
                    row["quantity"],
                    row["reorder_level"],
                    self._money(row["cost_price"]),
                    self._money(row["sale_price"]),
                    expiry.isoformat() if expiry else "-",
                ),
                tags=tags,
            )

    # ----------------------------------------------------------- selection helper
    def _selected_id(self):
        """Return the medicine_id (int) of the currently selected row, or None
        if nothing is selected."""
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    # -------------------------------------------------------------- add / edit
    def _add_medicine(self):
        """Open the add form with empty fields."""
        self._open_medicine_form(None)

    def _edit_selected(self):
        """Open the edit form pre-filled from the selected row, or warn if the
        client has not picked a row first."""
        medicine_id = self._selected_id()
        if medicine_id is None:
            messagebox.showwarning(
                "No medicine selected",
                "Select a medicine in the table first, then click Edit.",
            )
            return
        # Pull the full record fresh from the database so the form edits live
        # values rather than the formatted table strings.
        record = self.db.fetch_one(
            "SELECT medicine_id, name, supplier_id, batch_no, quantity, "
            "reorder_level, cost_price, sale_price, expiry_date "
            "FROM medicines WHERE medicine_id = %s",
            (medicine_id,),
        )
        if record is None:
            messagebox.showerror("Not found",
                                 "That medicine no longer exists.")
            self.refresh()
            return
        self._open_medicine_form(record)

    def _open_medicine_form(self, record):
        """Build the add/edit pop-up. 'record' is None for a new medicine, or a
        row dict to pre-fill for an edit. On a valid save it writes to the
        database, closes itself and refreshes the table."""
        is_edit = record is not None

        # Suppliers must exist before a medicine can be linked to one.
        suppliers = self._load_suppliers()
        if not suppliers:
            messagebox.showwarning(
                "No suppliers yet",
                "Add at least one supplier first (use 'Manage suppliers'); "
                "every medicine must belong to a supplier.",
            )
            return

        # A modal-ish Toplevel painted with the theme background.
        win = tk.Toplevel(self)
        win.title("Edit medicine" if is_edit else "Add medicine")
        win.configure(bg=theme.color("bg"))
        win.transient(self.winfo_toplevel())
        win.resizable(False, False)

        # A surface card holds the form so the labelled rows read well.
        body = theme.card(win)
        body.pack(fill="both", expand=True, padx=16, pady=16)
        inner = theme.frame(body, bg="surface")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        theme.label(
            inner, "Edit medicine" if is_edit else "Add a new medicine",
            kind="heading", fg="text", bg="surface",
        ).pack(anchor="w", pady=(0, 12))

        # --- Text/number fields, built with the shared field_row helper -------
        rows = {}
        for key, caption in (
            ("name", "Name"),
            ("batch_no", "Batch no"),
            ("quantity", "Quantity"),
            ("reorder_level", "Reorder level"),
            ("cost_price", "Cost price"),
            ("sale_price", "Sale price"),
            ("expiry_date", "Expiry date (YYYY-MM-DD)"),
        ):
            row_frame, entry = theme.field_row(inner, caption)
            row_frame.pack(fill="x", pady=6)
            rows[key] = entry

        # --- Supplier dropdown -------------------------------------------------
        # Display the supplier names; keep a parallel list of ids to map the
        # chosen name back to its supplier_id on save.
        supplier_names = [s["name"] for s in suppliers]
        supplier_ids = [s["supplier_id"] for s in suppliers]

        sup_frame = theme.frame(inner, bg="surface")
        sup_frame.pack(fill="x", pady=6)
        theme.label(sup_frame, "Supplier", kind="small", fg="muted",
                    bg="surface").pack(anchor="w")
        supplier_cb = theme.combobox(sup_frame, supplier_names, width=28)
        supplier_cb.pack(fill="x", pady=(2, 0))

        # --- Pre-fill on edit --------------------------------------------------
        if is_edit:
            rows["name"].insert(0, record["name"] or "")
            rows["batch_no"].insert(0, record["batch_no"] or "")
            rows["quantity"].insert(0, str(record["quantity"]))
            rows["reorder_level"].insert(0, str(record["reorder_level"]))
            rows["cost_price"].insert(0, self._money(record["cost_price"]))
            rows["sale_price"].insert(0, self._money(record["sale_price"]))
            if record["expiry_date"]:
                rows["expiry_date"].insert(0, record["expiry_date"].isoformat())
            # Select the medicine's current supplier in the dropdown.
            if record["supplier_id"] in supplier_ids:
                supplier_cb.current(supplier_ids.index(record["supplier_id"]))

        # --- Save handler ------------------------------------------------------
        def save():
            """Validate every field and only write to the database if all checks
            pass (Criteria A requires input validation)."""
            name = rows["name"].get().strip()
            batch = rows["batch_no"].get().strip()

            # Name is the one mandatory free-text field.
            if not name:
                messagebox.showerror("Missing name",
                                     "Medicine name cannot be blank.")
                return

            # Quantity and reorder must be non-negative whole numbers.
            quantity = self._parse_int(rows["quantity"].get(), "Quantity")
            if quantity is None:
                return
            reorder = self._parse_int(rows["reorder_level"].get(),
                                      "Reorder level")
            if reorder is None:
                return

            # Cost and sale must be non-negative numbers.
            cost = self._parse_money(rows["cost_price"].get(), "Cost price")
            if cost is None:
                return
            sale = self._parse_money(rows["sale_price"].get(), "Sale price")
            if sale is None:
                return

            # Expiry must parse as a real YYYY-MM-DD date.
            expiry_text = rows["expiry_date"].get().strip()
            try:
                expiry = datetime.datetime.strptime(
                    expiry_text, "%Y-%m-%d"
                ).date()
            except ValueError:
                messagebox.showerror(
                    "Invalid expiry date",
                    "Enter the expiry date as YYYY-MM-DD (for example "
                    "2026-12-31).",
                )
                return

            # A supplier must be chosen.
            choice = supplier_cb.current()
            if choice < 0:
                messagebox.showerror("No supplier",
                                     "Choose a supplier for this medicine.")
                return
            supplier_id = supplier_ids[choice]

            # All checks passed: write the row. INSERT for a new medicine (with
            # created_at set now), UPDATE for an edit.
            if is_edit:
                self.db.execute(
                    "UPDATE medicines SET name=%s, supplier_id=%s, batch_no=%s, "
                    "quantity=%s, reorder_level=%s, cost_price=%s, "
                    "sale_price=%s, expiry_date=%s WHERE medicine_id=%s",
                    (name, supplier_id, batch, quantity, reorder, cost, sale,
                     expiry, record["medicine_id"]),
                )
            else:
                self.db.execute(
                    "INSERT INTO medicines (name, supplier_id, batch_no, "
                    "quantity, reorder_level, cost_price, sale_price, "
                    "expiry_date, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (name, supplier_id, batch, quantity, reorder, cost, sale,
                     expiry, datetime.datetime.now()),
                )

            win.destroy()
            self.refresh()

        # --- Form buttons ------------------------------------------------------
        buttons = theme.frame(inner, bg="surface")
        buttons.pack(fill="x", pady=(16, 0))
        theme.button(buttons, "Save", command=save,
                     kind="primary").pack(side="right")
        theme.button(buttons, "Cancel", command=win.destroy,
                     kind="ghost").pack(side="right", padx=6)

    # ----------------------------------------------------------- validation aids
    def _parse_int(self, raw, field_name):
        """Parse a non-negative integer from a form field. Shows an error and
        returns None if the value is blank, not a whole number, or negative."""
        raw = raw.strip()
        try:
            value = int(raw)
        except ValueError:
            messagebox.showerror(
                "Invalid number",
                "{} must be a whole number.".format(field_name),
            )
            return None
        if value < 0:
            messagebox.showerror(
                "Invalid number",
                "{} cannot be negative.".format(field_name),
            )
            return None
        return value

    def _parse_money(self, raw, field_name):
        """Parse a non-negative decimal amount from a form field. Shows an error
        and returns None if the value is blank, not a number, or negative."""
        raw = raw.strip()
        try:
            value = float(raw)
        except ValueError:
            messagebox.showerror(
                "Invalid number",
                "{} must be a number (for example 1.20).".format(field_name),
            )
            return None
        if value < 0:
            messagebox.showerror(
                "Invalid number",
                "{} cannot be negative.".format(field_name),
            )
            return None
        return value

    # --------------------------------------------------------------- delete row
    def _delete_selected(self):
        """Confirm and delete the selected medicine, then refresh. Warns if no
        row is selected."""
        medicine_id = self._selected_id()
        if medicine_id is None:
            messagebox.showwarning(
                "No medicine selected",
                "Select a medicine in the table first, then click Delete.",
            )
            return

        # Read the name back so the confirmation names the exact record.
        values = self.tree.item(str(medicine_id), "values")
        name = values[0] if values else "this medicine"
        if not messagebox.askyesno(
            "Delete medicine",
            "Delete '{}' from your stock? This cannot be undone.".format(name),
        ):
            return

        self.db.execute("DELETE FROM medicines WHERE medicine_id = %s",
                        (medicine_id,))
        self.refresh()

    # ----------------------------------------------------------- manage suppliers
    def _open_suppliers(self):
        """Open the supplier manager: a small table of existing suppliers plus a
        form to add a new one. Medicines need suppliers to exist, so this is
        reachable directly from the stock screen."""
        win = tk.Toplevel(self)
        win.title("Manage suppliers")
        win.configure(bg=theme.color("bg"))
        win.transient(self.winfo_toplevel())
        win.resizable(False, False)

        body = theme.card(win)
        body.pack(fill="both", expand=True, padx=16, pady=16)
        inner = theme.frame(body, bg="surface")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        theme.label(inner, "Suppliers", kind="heading", fg="text",
                    bg="surface").pack(anchor="w", pady=(0, 10))

        # --- Existing suppliers table -----------------------------------------
        sup_cols = ("name", "contact", "phone", "email")
        sup_tree = ttk.Treeview(
            inner, columns=sup_cols, show="headings",
            style="Greenline.Treeview", height=8,
        )
        for col, head, width in (
            ("name", "Name", 170),
            ("contact", "Contact", 140),
            ("phone", "Phone", 120),
            ("email", "Email", 180),
        ):
            sup_tree.heading(col, text=head, anchor="w")
            sup_tree.column(col, width=width, anchor="w", stretch=True)
        sup_tree.pack(fill="both", expand=True)

        def reload_suppliers():
            """Re-query and repopulate the supplier table."""
            for item in sup_tree.get_children():
                sup_tree.delete(item)
            for s in self.db.fetch_all(
                "SELECT name, contact_person, phone, email FROM suppliers "
                "ORDER BY name ASC"
            ):
                sup_tree.insert(
                    "", "end",
                    values=(s["name"], s["contact_person"] or "-",
                            s["phone"] or "-", s["email"] or "-"),
                )

        reload_suppliers()

        # --- Add-supplier form -------------------------------------------------
        theme.label(inner, "Add a supplier", kind="body_bold", fg="primary",
                    bg="surface").pack(anchor="w", pady=(16, 6))

        form_rows = {}
        for key, caption in (
            ("name", "Name (required)"),
            ("contact_person", "Contact person"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("address", "Address"),
        ):
            row_frame, entry = theme.field_row(inner, caption)
            row_frame.pack(fill="x", pady=4)
            form_rows[key] = entry

        def add_supplier():
            """Validate the supplier name (the only required field) and insert,
            then refresh the list above and clear the form."""
            name = form_rows["name"].get().strip()
            if not name:
                messagebox.showerror("Missing name",
                                     "Supplier name cannot be blank.")
                return
            self.db.execute(
                "INSERT INTO suppliers (name, contact_person, phone, email, "
                "address) VALUES (%s,%s,%s,%s,%s)",
                (
                    name,
                    form_rows["contact_person"].get().strip() or None,
                    form_rows["phone"].get().strip() or None,
                    form_rows["email"].get().strip() or None,
                    form_rows["address"].get().strip() or None,
                ),
            )
            # Clear the form for the next entry and rebuild the list.
            for entry in form_rows.values():
                entry.delete(0, "end")
            reload_suppliers()

        buttons = theme.frame(inner, bg="surface")
        buttons.pack(fill="x", pady=(14, 0))
        theme.button(buttons, "Add supplier", command=add_supplier,
                     kind="primary").pack(side="right")
        theme.button(buttons, "Close", command=win.destroy,
                     kind="ghost").pack(side="right", padx=6)
