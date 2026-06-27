"""The dashboard: the first screen shown after login, giving the client an
at-a-glance overview of the whole business.

It pulls a handful of summary figures (stock counts, stock value, receivables)
into a row of metric cards, then surfaces the two things the client most wants
flagged automatically: medicines expiring soon and medicines running low on
stock (Criteria A, Appendix 1 point 9). Everything is loaded in refresh() rather
than __init__ so the numbers are always re-queried each time the screen is
opened and reflect edits made on the other views.
"""

import datetime
import tkinter as tk

from greenline import config
from greenline import theme


class DashboardView(tk.Frame):
    """The overview screen. The static page header is built once in __init__;
    all live figures live inside a content frame that refresh() rebuilds from
    fresh database queries."""

    def __init__(self, parent, db):
        super().__init__(parent, bg=theme.color("bg"))
        self.db = db

        # Outer padding so the content does not touch the window edges.
        outer = theme.frame(self, bg="bg")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        # --- Page header (static) ---------------------------------------------
        header = theme.frame(outer, bg="bg")
        header.pack(fill="x", anchor="w")
        theme.heading(header, "Dashboard", bg="bg").pack(anchor="w")
        theme.label(
            header,
            "A live overview of your stock, clinics and alerts.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(2, 0))

        # --- Content frame (rebuilt on every refresh) -------------------------
        # Keeping the live figures in their own frame lets refresh() simply wipe
        # and redraw everything below the header without touching the title.
        self.content = theme.frame(outer, bg="bg")
        self.content.pack(fill="both", expand=True, pady=(20, 0))

    # ------------------------------------------------------------------ helpers
    def _money(self, value):
        """Format a numeric amount as a rupee string with thousands separators.
        DECIMAL columns arrive as Python Decimal, so wrap in float() first; a
        missing/NULL aggregate (None) is treated as zero."""
        return "Rs {:,.2f}".format(float(value or 0))

    def _clear_content(self):
        """Remove every widget currently inside the content frame so refresh()
        can redraw from scratch without stacking old data on top."""
        for child in self.content.winfo_children():
            child.destroy()

    # ------------------------------------------------------------------ refresh
    def refresh(self):
        """Re-query the database and redraw the metric cards and alert panels.
        Called by the navigation shell every time the dashboard is shown."""
        self._clear_content()
        self._build_metric_row()
        self._build_alert_panels()

    # ------------------------------------------------------------- metric cards
    def _build_metric_row(self):
        """Query the five headline figures and lay them out as a row of cards."""
        # Each figure is a single aggregate query. COALESCE guards against NULL
        # results when a table is empty so the cards always show a number.
        total_medicines = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM medicines"
        )["n"]
        total_units = self.db.fetch_one(
            "SELECT COALESCE(SUM(quantity), 0) AS n FROM medicines"
        )["n"]
        stock_value = self.db.fetch_one(
            "SELECT COALESCE(SUM(quantity * cost_price), 0) AS v FROM medicines"
        )["v"]
        active_clinics = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM clinics"
        )["n"]
        # Amount owed across all clinics: charges add to the balance, payments
        # subtract from it (see schema note on clinic_transactions).
        receivables = self.db.fetch_one(
            "SELECT COALESCE(SUM(CASE WHEN txn_type='charge' THEN amount "
            "ELSE -amount END), 0) AS owed FROM clinic_transactions"
        )["owed"]

        # (big value, caption) for each card, in display order.
        metrics = [
            (str(total_medicines), "Total medicines"),
            (str(int(total_units)), "Total stock units"),
            (self._money(stock_value), "Stock value (at cost)"),
            (str(active_clinics), "Active clinics"),
            (self._money(receivables), "Receivables owed"),
        ]

        # A horizontal row that shares its width evenly between the cards.
        row = theme.frame(self.content, bg="bg")
        row.pack(fill="x")
        for value, caption in metrics:
            self._metric_card(row, value, caption)

    def _metric_card(self, parent, value, caption):
        """Build one metric card: a large primary-coloured number above a small
        muted caption, packed so the cards expand evenly to fill the row."""
        card = theme.card(parent)
        card.pack(side="left", fill="both", expand=True, padx=6)
        # Inner padding gives the figures room to breathe inside the card.
        inner = theme.frame(card, bg="surface")
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        theme.label(inner, value, kind="title", fg="primary",
                    bg="surface").pack(anchor="w")
        theme.label(inner, caption, kind="small", fg="muted",
                    bg="surface").pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------- alert panels
    def _build_alert_panels(self):
        """Lay the expiring-soon and low-stock panels side by side beneath the
        metric cards."""
        panels = theme.frame(self.content, bg="bg")
        panels.pack(fill="both", expand=True, pady=(18, 0))

        self._build_expiry_panel(panels)
        self._build_low_stock_panel(panels)

    def _panel(self, parent, title):
        """Create a titled card and return the inner frame rows should pack into.
        Shared by both alert panels so they look identical."""
        card = theme.card(parent)
        card.pack(side="left", fill="both", expand=True, padx=6)
        inner = theme.frame(card, bg="surface")
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        theme.label(inner, title, kind="heading", fg="text",
                    bg="surface").pack(anchor="w", pady=(0, 10))
        return inner

    def _empty_line(self, parent):
        """Placeholder shown when a panel has no items to list."""
        theme.label(parent, "Nothing to show", kind="small", fg="muted",
                    bg="surface").pack(anchor="w")

    def _build_expiry_panel(self, parent):
        """List medicines expiring within the warning window. Already-expired
        batches are shown in danger red; soon-to-expire ones in amber."""
        inner = self._panel(parent, "Expiring soon")

        today = datetime.date.today()
        cutoff = today + datetime.timedelta(days=config.EXPIRY_WARNING_DAYS)
        # Pull batches dated on or before the cutoff (expired ones included) so
        # the panel doubles as an "already expired" warning. Soonest first.
        rows = self.db.fetch_all(
            "SELECT name, batch_no, expiry_date FROM medicines "
            "WHERE expiry_date IS NOT NULL AND expiry_date <= %s "
            "ORDER BY expiry_date ASC",
            (cutoff,),
        )

        if not rows:
            self._empty_line(inner)
            return

        for row in rows:
            expiry = row["expiry_date"]
            days_left = (expiry - today).days
            # Build the right-hand status text and pick its colour: red for an
            # already-expired batch, amber for one merely nearing expiry.
            if days_left < 0:
                status_text = "EXPIRED"
                status_fg = "danger"
            else:
                status_text = "{} days left".format(days_left)
                status_fg = "amber"

            line = theme.frame(inner, bg="surface")
            line.pack(fill="x", pady=3)
            # Left side: medicine name, batch and the formatted expiry date.
            detail = "{}  -  batch {}  -  exp {}".format(
                row["name"], row["batch_no"] or "-", expiry.isoformat()
            )
            theme.label(line, detail, kind="small", fg="text",
                        bg="surface").pack(side="left", anchor="w")
            # Right side: the coloured days-left / EXPIRED status.
            theme.label(line, status_text, kind="small", fg=status_fg,
                        bg="surface").pack(side="right", anchor="e")

    def _build_low_stock_panel(self, parent):
        """List medicines at or below their reorder level, with the current
        quantity highlighted in amber so it stands out."""
        inner = self._panel(parent, "Low stock")

        # quantity <= reorder_level is the agreed "running low" rule.
        rows = self.db.fetch_all(
            "SELECT name, quantity, reorder_level FROM medicines "
            "WHERE quantity <= reorder_level ORDER BY quantity ASC"
        )

        if not rows:
            self._empty_line(inner)
            return

        for row in rows:
            line = theme.frame(inner, bg="surface")
            line.pack(fill="x", pady=3)
            # Medicine name on the left.
            theme.label(line, row["name"], kind="small", fg="text",
                        bg="surface").pack(side="left", anchor="w")
            # Amber "qty X / reorder Y" on the right to draw the eye.
            qty_text = "qty {} / reorder {}".format(
                row["quantity"], row["reorder_level"]
            )
            theme.label(line, qty_text, kind="small", fg="amber",
                        bg="surface").pack(side="right", anchor="e")
