"""The "Record a sale" screen for Greenline Pharmacy.

This is the one screen that turns stock into a sale: it inserts a row into the
sales table (which feeds the Profit & Loss report and the sales charts) and, in
the same action, decreases the medicine's quantity so the inventory stays
accurate. Recording a sale captures the medicine's current cost price on the
sale row, so profit stays correct even if the cost changes later.

Validation here is important (Criteria A): the user cannot sell more units than
are in stock (which would drive stock negative), nor enter a blank/zero/negative
quantity or price. Each recorded sale can also be reversed, which deletes the
sale row and returns the units to stock so a mistaken entry is easy to undo.
"""

import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from greenline import theme


class SalesView(tk.Frame):
    """A Tk frame with a "record a sale" form on the left and a list of recent
    sales on the right. Follows the same (parent, db) + refresh() contract as
    the other screens so the navigation shell can treat it identically."""

    def __init__(self, parent, db):
        super().__init__(parent, bg=theme.color("bg"))
        self.db = db
        # These lists keep the dropdown positions aligned with database ids, so
        # the selected index can be mapped back to a medicine / clinic row.
        self._med_rows = []          # medicine rows, parallel to the medicine dropdown
        self._clinic_ids = []        # clinic ids (None first = walk-in counter)

        self._build_header()
        self._build_body()
        # Populate the dropdowns and the recent-sales table from the database.
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build_header(self):
        """The page title and a one-line explanation at the top of the screen."""
        head = theme.frame(self, bg="bg")
        head.pack(fill="x", padx=24, pady=(22, 6))
        theme.heading(head, "Record a Sale").pack(anchor="w")
        theme.label(head, "Sell stock at the counter or to a clinic; stock is "
                    "updated automatically.", kind="small", fg="muted",
                    bg="bg").pack(anchor="w")

    def _build_body(self):
        """Split the screen into the sale form (left) and recent sales (right)."""
        body = theme.frame(self, bg="bg")
        body.pack(fill="both", expand=True, padx=24, pady=12)

        self._build_form(body)
        self._build_recent(body)

    def _build_form(self, parent):
        """The data-entry card where a new sale is composed."""
        card = theme.card(parent)
        card.pack(side="left", fill="y", padx=(0, 16))
        pad = theme.frame(card, bg="surface")
        pad.pack(fill="both", expand=True, padx=18, pady=18)

        theme.label(pad, "New sale", kind="heading", fg="primary",
                    bg="surface").pack(anchor="w", pady=(0, 10))

        # Medicine to sell. The dropdown shows each medicine with its current
        # stock so the user can see availability while choosing.
        theme.label(pad, "Medicine", kind="small", fg="muted",
                    bg="surface").pack(anchor="w")
        self.med_cb = theme.combobox(pad, [], width=30)
        self.med_cb.pack(fill="x", pady=(2, 10))
        # When the medicine changes, auto-fill the price and show stock left.
        self.med_cb.bind("<<ComboboxSelected>>", self._on_medicine_change)

        # Live read-out of how many units remain for the chosen medicine.
        self.stock_label = theme.label(pad, "", kind="small", fg="muted",
                                       bg="surface")
        self.stock_label.pack(anchor="w", pady=(0, 8))

        # Customer: either the walk-in counter (no clinic) or a clinic account.
        theme.label(pad, "Customer", kind="small", fg="muted",
                    bg="surface").pack(anchor="w")
        self.customer_cb = theme.combobox(pad, [], width=30)
        self.customer_cb.pack(fill="x", pady=(2, 10))

        # Quantity, unit price and date inputs built with the shared field helper.
        qty_row, self.qty_entry = theme.field_row(pad, "Quantity")
        qty_row.pack(fill="x", pady=(0, 8))
        price_row, self.price_entry = theme.field_row(pad, "Unit price (Rs)")
        price_row.pack(fill="x", pady=(0, 8))
        date_row, self.date_entry = theme.field_row(pad, "Date (YYYY-MM-DD)")
        date_row.pack(fill="x", pady=(0, 8))
        self.date_entry.insert(0, datetime.date.today().isoformat())

        # Recompute the running line total whenever quantity or price changes.
        self.qty_entry.bind("<KeyRelease>", lambda _e: self._update_total())
        self.price_entry.bind("<KeyRelease>", lambda _e: self._update_total())

        # A bold preview of quantity x price so the user sees the sale value.
        self.total_label = theme.label(pad, "Line total: Rs 0.00",
                                       kind="body_bold", fg="primary", bg="surface")
        self.total_label.pack(anchor="w", pady=(6, 12))

        theme.button(pad, "Record sale", command=self._record_sale,
                     kind="primary").pack(fill="x")

    def _build_recent(self, parent):
        """The table of recently recorded sales, newest first."""
        card = theme.card(parent)
        card.pack(side="left", fill="both", expand=True)
        pad = theme.frame(card, bg="surface")
        pad.pack(fill="both", expand=True, padx=16, pady=16)

        theme.label(pad, "Recent sales", kind="heading", fg="primary",
                    bg="surface").pack(anchor="w", pady=(0, 8))

        # The sales table. Columns mirror what a receipt would show.
        columns = ("date", "medicine", "customer", "qty", "price", "total")
        headings = {"date": "Date", "medicine": "Medicine", "customer": "Customer",
                    "qty": "Qty", "price": "Unit price", "total": "Total"}
        widths = {"date": 90, "medicine": 150, "customer": 140, "qty": 50,
                  "price": 90, "total": 100}
        table_wrap = theme.frame(pad, bg="surface")
        table_wrap.pack(fill="both", expand=True)
        self.recent_tree = ttk.Treeview(
            table_wrap, columns=columns, show="headings",
            style="Greenline.Treeview", height=14)
        for col in columns:
            # Numbers are right-aligned, text is left-aligned for readability.
            anchor = "e" if col in ("qty", "price", "total") else "w"
            self.recent_tree.heading(col, text=headings[col], anchor=anchor)
            self.recent_tree.column(col, width=widths[col], anchor=anchor, stretch=True)
        scroll = ttk.Scrollbar(table_wrap, orient="vertical",
                               command=self.recent_tree.yview)
        self.recent_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.recent_tree.pack(side="left", fill="both", expand=True)

        # Reversing a sale puts the units back into stock, so it sits with the
        # table as a clearly-labelled, less prominent (ghost) action.
        theme.button(pad, "Reverse selected sale (return to stock)",
                     command=self._delete_sale, kind="ghost").pack(anchor="w",
                                                                   pady=(10, 0))

    # ---------------------------------------------------------------- helpers
    def _money(self, value):
        """Format a number as a rupee string; DECIMALs arrive as Decimal."""
        return "Rs {:,.2f}".format(float(value or 0))

    def _selected_medicine(self):
        """Return the medicine row currently chosen in the dropdown, or None."""
        index = self.med_cb.current()
        if 0 <= index < len(self._med_rows):
            return self._med_rows[index]
        return None

    def _on_medicine_change(self, _event=None):
        """When a medicine is picked, pre-fill its sale price and show how many
        units are in stock so the user has the context to enter a quantity."""
        med = self._selected_medicine()
        if med is None:
            return
        # Replace whatever is in the price box with this medicine's sale price.
        self.price_entry.delete(0, "end")
        self.price_entry.insert(0, "{:.2f}".format(float(med["sale_price"])))
        self.stock_label.config(text="In stock: %d unit(s)" % med["quantity"])
        self._update_total()

    def _update_total(self):
        """Refresh the "line total" preview from the current quantity and price,
        ignoring (rather than erroring on) half-typed numbers."""
        try:
            qty = int(self.qty_entry.get())
            price = float(self.price_entry.get())
            self.total_label.config(text="Line total: " + self._money(qty * price))
        except ValueError:
            self.total_label.config(text="Line total: Rs 0.00")

    # ------------------------------------------------------------------ data
    def refresh(self):
        """Reload the medicine and customer dropdowns and the recent-sales table.
        Called whenever the screen is shown so it reflects edits made elsewhere
        (e.g. new medicines, or stock changed by another sale)."""
        self._load_medicines()
        self._load_customers()
        self._load_recent()

    def _load_medicines(self):
        """Fill the medicine dropdown with every medicine and its stock level."""
        self._med_rows = self.db.fetch_all(
            "SELECT medicine_id, name, quantity, sale_price, cost_price "
            "FROM medicines ORDER BY name")
        labels = ["%s  (%d in stock)" % (m["name"], m["quantity"])
                  for m in self._med_rows]
        self.med_cb.set_values(labels)
        # Re-apply the price/stock read-out for whatever is now selected.
        self._on_medicine_change()

    def _load_customers(self):
        """Fill the customer dropdown: a walk-in counter option followed by every
        clinic. The parallel _clinic_ids list maps a choice back to a clinic id
        (None for the walk-in counter / retail sale)."""
        clinics = self.db.fetch_all("SELECT clinic_id, name FROM clinics ORDER BY name")
        self._clinic_ids = [None] + [c["clinic_id"] for c in clinics]
        labels = ["Walk-in counter"] + [c["name"] for c in clinics]
        self.customer_cb.set_values(labels)
        self.customer_cb.current(0)

    def _load_recent(self):
        """Reload the recent-sales table, newest first. Names are pulled in via
        LEFT JOINs so a sale still shows even if its medicine or clinic was later
        removed."""
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
        rows = self.db.fetch_all(
            "SELECT s.sale_id, s.sale_date, s.quantity, s.unit_price, s.total, "
            "       COALESCE(m.name, '(removed)') AS medicine, "
            "       COALESCE(c.name, 'Walk-in counter') AS customer "
            "FROM sales s "
            "LEFT JOIN medicines m ON s.medicine_id = m.medicine_id "
            "LEFT JOIN clinics c ON s.clinic_id = c.clinic_id "
            "ORDER BY s.sale_date DESC, s.sale_id DESC LIMIT 100")
        for r in rows:
            # The row id (iid) is the sale_id so a selected row can be reversed.
            self.recent_tree.insert(
                "", "end", iid=str(r["sale_id"]),
                values=(r["sale_date"], r["medicine"], r["customer"],
                        r["quantity"], self._money(r["unit_price"]),
                        self._money(r["total"])))

    # ----------------------------------------------------------------- actions
    def _record_sale(self):
        """Validate the form, then insert the sale and reduce stock atomically.
        Every failure path shows a clear message and changes nothing."""
        med = self._selected_medicine()
        if med is None:
            messagebox.showwarning("No medicine", "Please choose a medicine to sell.")
            return

        # Quantity must be a whole number greater than zero.
        try:
            qty = int(self.qty_entry.get())
        except ValueError:
            messagebox.showerror("Invalid quantity", "Quantity must be a whole number.")
            return
        if qty <= 0:
            messagebox.showerror("Invalid quantity", "Quantity must be greater than zero.")
            return
        # Cannot sell more than is in stock - this is what keeps stock from going
        # negative (Criteria A: the user cannot have a negative number of stock).
        if qty > med["quantity"]:
            messagebox.showerror(
                "Not enough stock",
                "Only %d unit(s) of %s are in stock." % (med["quantity"], med["name"]))
            return

        # Unit price must be a valid, non-negative number.
        try:
            price = float(self.price_entry.get())
        except ValueError:
            messagebox.showerror("Invalid price", "Unit price must be a number.")
            return
        if price < 0:
            messagebox.showerror("Invalid price", "Unit price cannot be negative.")
            return

        # Date must parse as YYYY-MM-DD.
        try:
            sale_date = datetime.datetime.strptime(
                self.date_entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Invalid date", "Use the date format YYYY-MM-DD.")
            return

        # Map the customer choice to a clinic id (None for a counter sale).
        cust_index = self.customer_cb.current()
        clinic_id = self._clinic_ids[cust_index] if 0 <= cust_index < len(self._clinic_ids) else None

        # Capture the cost at sale time so profit reporting stays accurate.
        unit_cost = float(med["cost_price"])
        total = round(qty * price, 2)

        # Insert the sale, then subtract the units from the medicine's stock.
        self.db.execute(
            "INSERT INTO sales (sale_date, medicine_id, clinic_id, quantity, "
            "unit_price, unit_cost, total) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (sale_date, med["medicine_id"], clinic_id, qty, price, unit_cost, total))
        self.db.execute(
            "UPDATE medicines SET quantity = quantity - %s WHERE medicine_id = %s",
            (qty, med["medicine_id"]))

        messagebox.showinfo(
            "Sale recorded",
            "Sold %d x %s for %s." % (qty, med["name"], self._money(total)))

        # Reset the quantity and reload everything so stock figures update.
        self.qty_entry.delete(0, "end")
        self.refresh()

    def _delete_sale(self):
        """Reverse the selected sale: delete the row and return its units to
        stock (if the medicine still exists), after confirming with the user."""
        selection = self.recent_tree.selection()
        if not selection:
            messagebox.showwarning("No sale selected",
                                   "Select a sale in the list to reverse it.")
            return
        sale_id = int(selection[0])
        sale = self.db.fetch_one(
            "SELECT medicine_id, quantity FROM sales WHERE sale_id = %s", (sale_id,))
        if sale is None:
            return
        if not messagebox.askyesno(
                "Reverse sale",
                "Delete this sale and return %d unit(s) to stock?" % sale["quantity"]):
            return

        # Put the units back only if the medicine still exists (it may have been
        # deleted, in which case its sale rows have a NULL medicine_id).
        if sale["medicine_id"] is not None:
            self.db.execute(
                "UPDATE medicines SET quantity = quantity + %s WHERE medicine_id = %s",
                (sale["quantity"], sale["medicine_id"]))
        self.db.execute("DELETE FROM sales WHERE sale_id = %s", (sale_id,))
        self.refresh()
