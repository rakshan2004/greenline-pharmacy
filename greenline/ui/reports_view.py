"""The reports screen: the figures the client asked for so he "doesn't sit
there adding things up himself" (Criteria A).

Three reports live here, switched with a row of selector buttons:

  1. Receivables by clinic - how much each clinic still owes (charges minus
     payments), with clinics in the red tinted amber and a grand total.
  2. Profit & loss - revenue, cost of goods and net profit over a date range
     the user picks, plus a per-medicine breakdown.
  3. Stock by supplier - how many medicines, how many units and how much the
     standing stock is worth, grouped per supplier.

Each report is queried fresh from the database when it is shown, so the numbers
always reflect the latest edits made on the other views. refresh() simply
re-runs whichever report is currently selected, which the navigation shell calls
every time this screen is opened.
"""

import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from greenline import theme


# Background tint for a clinic that still owes money, to draw the eye the same
# way the amber low-stock highlight does on the medicines screen.
TINT_OWED = "#3A2E12"

# How far back the profit-and-loss report looks by default. The client usually
# reviews the last quarter, so the start date defaults to roughly 90 days ago.
DEFAULT_PL_DAYS = 90


class ReportsView(tk.Frame):
    """The reports screen. The page header and report selector are built once in
    __init__; the chosen report is drawn into a content frame that is wiped and
    rebuilt whenever the selection changes or refresh() is called."""

    def __init__(self, parent, db):
        super().__init__(parent, bg=theme.color("bg"))
        self.db = db

        # The reports in display order: (key, button caption, builder method).
        # Keyed by a short string so the selector and refresh() can agree on
        # which report is active without depending on widget state.
        self._reports = (
            ("receivables", "Receivables by clinic", self._build_receivables),
            ("profit_loss", "Profit & loss", self._build_profit_loss),
            ("stock", "Stock by supplier", self._build_stock_by_supplier),
        )
        # Which report is currently shown; defaults to the first one.
        self._current = self._reports[0][0]
        # Holds the selector buttons so the active one can be highlighted.
        self._selector_buttons = {}

        # Outer padding so the content does not touch the window edges.
        outer = theme.frame(self, bg="bg")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        # --- Page header (static) ---------------------------------------------
        header = theme.frame(outer, bg="bg")
        header.pack(fill="x", anchor="w")
        theme.heading(header, "Reports", bg="bg").pack(anchor="w")
        theme.label(
            header,
            "Receivables, profit and loss, and stock value - worked out for you.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(2, 0))

        # --- Report selector (static) -----------------------------------------
        # A row of buttons; clicking one switches the report shown below.
        selector = theme.frame(outer, bg="bg")
        selector.pack(fill="x", pady=(18, 0))
        for key, caption, _builder in self._reports:
            btn = theme.button(
                selector, caption,
                command=lambda k=key: self._select(k),
                kind="ghost",
            )
            btn.pack(side="left", padx=(0, 8))
            self._selector_buttons[key] = btn

        # --- Content frame (rebuilt on every switch / refresh) ----------------
        # Keeping each report inside its own frame lets us simply wipe and redraw
        # everything below the selector without disturbing the header.
        self.content = theme.frame(outer, bg="bg")
        self.content.pack(fill="both", expand=True, pady=(18, 0))

        # Draw the default report straight away so the screen is never blank.
        self._render()

    # ------------------------------------------------------------------ helpers
    def _money(self, value):
        """Format a numeric amount as a rupee string with thousands separators.
        DECIMAL columns arrive as Python Decimal, so wrap in float() first; a
        missing/NULL aggregate (None) is treated as zero."""
        return "Rs {:,.2f}".format(float(value or 0))

    def _clear_content(self):
        """Remove every widget currently inside the content frame so a report
        can redraw from scratch without stacking old data on top."""
        for child in self.content.winfo_children():
            child.destroy()

    def _select(self, key):
        """Switch to the report identified by key and redraw it."""
        self._current = key
        self._render()

    def _render(self):
        """Wipe the content area, highlight the active selector button and run
        the builder for the currently-selected report."""
        self._clear_content()
        # Repaint the selector so the active button stands out in brand green
        # while the others stay in the subtle "ghost" style. We update the
        # button's stored _rest/_hover colours (not just bg) so the hover
        # handlers keep the active tab green even after the mouse leaves it.
        for key, btn in self._selector_buttons.items():
            active = key == self._current
            rest = theme.color("primary") if active else theme.color("surface_alt")
            hover = theme.color("primary_dark") if active else theme.color("surface_alt")
            btn._rest = rest
            btn._hover = hover
            btn.config(bg=rest,
                       fg=theme.color("bg") if active else theme.color("text"))
        # Look up and run the builder paired with the active key.
        for key, _caption, builder in self._reports:
            if key == self._current:
                builder()
                break

    # ------------------------------------------------------------------ refresh
    def refresh(self):
        """Re-run whichever report is currently selected so the figures stay
        fresh when the user returns to this screen. Called by the navigation
        shell each time the reports view is shown."""
        self._render()

    # ------------------------------------------------- shared table scaffolding
    def _make_table(self, parent, columns, headings, right_aligned, height=12):
        """Build a bordered card holding a Treeview with a vertical scrollbar.
        Returns the Treeview so the caller can fill it. Shared by all three
        reports so every table looks identical."""
        card = theme.card(parent)
        card.pack(fill="both", expand=True)
        inner = theme.frame(card, bg="surface")
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        tree = ttk.Treeview(
            inner, columns=columns, show="headings",
            style="Greenline.Treeview", height=height,
        )
        for col in columns:
            # Numeric/money columns are right-aligned so figures line up.
            anchor = "e" if col in right_aligned else "w"
            tree.heading(col, text=headings[col], anchor=anchor)
            # The first (name) column is given more room than the figures.
            width = 220 if col == columns[0] else 130
            tree.column(col, width=width, anchor=anchor, stretch=True)

        # A vertical scrollbar for long lists.
        scroll = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        # Pre-configure the two row tints the reports use: amber for a clinic in
        # debt, and a brand-green bold-ish look for the TOTAL row.
        tree.tag_configure("owed", background=TINT_OWED,
                           foreground=theme.color("amber"))
        tree.tag_configure("total", foreground=theme.color("primary"),
                           font=theme.font("body_bold"))
        return tree

    # ============================================================ 1. receivables
    def _build_receivables(self):
        """Show one row per clinic with total charged, total paid and the
        balance still owed (charged - paid). Clinics in debt are tinted amber,
        and a TOTAL row sums every balance."""
        theme.label(
            self.content,
            "How much each clinic still owes you (charges minus payments).",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(0, 10))

        columns = ("clinic", "charged", "paid", "balance")
        headings = {
            "clinic": "Clinic", "charged": "Total charged",
            "paid": "Total paid", "balance": "Balance owed",
        }
        right_aligned = {"charged", "paid", "balance"}
        tree = self._make_table(self.content, columns, headings, right_aligned)

        # LEFT JOIN so clinics that have never had a ledger entry still appear
        # with zeros. The CASE splits the single amount column into charged and
        # paid totals; COALESCE keeps the sums at 0 rather than NULL.
        rows = self.db.fetch_all(
            "SELECT c.clinic_id, c.name, "
            "  COALESCE(SUM(CASE WHEN t.txn_type='charge' THEN t.amount END), 0) AS charged, "
            "  COALESCE(SUM(CASE WHEN t.txn_type='payment' THEN t.amount END), 0) AS paid "
            "FROM clinics c "
            "LEFT JOIN clinic_transactions t ON t.clinic_id = c.clinic_id "
            "GROUP BY c.clinic_id, c.name "
            "ORDER BY c.name ASC"
        )

        total_balance = 0.0
        for row in rows:
            charged = float(row["charged"] or 0)
            paid = float(row["paid"] or 0)
            balance = charged - paid
            total_balance += balance
            # Tint the row amber only when the clinic still owes money.
            tags = ("owed",) if balance > 0 else ()
            tree.insert(
                "", "end",
                values=(
                    row["name"],
                    self._money(charged),
                    self._money(paid),
                    self._money(balance),
                ),
                tags=tags,
            )

        # Grand total row across all clinics, styled in the brand green.
        tree.insert(
            "", "end",
            values=("TOTAL", "", "", self._money(total_balance)),
            tags=("total",),
        )

    # ============================================================ 2. profit/loss
    def _build_profit_loss(self):
        """Date inputs and a run button, then the revenue / cost / profit summary
        plus a per-medicine breakdown for the chosen range."""
        theme.label(
            self.content,
            "Pick a date range, then run the report to see your profit or loss.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(0, 10))

        # --- Date controls, grouped in a card ---------------------------------
        controls_card = theme.card(self.content)
        controls_card.pack(fill="x")
        controls = theme.frame(controls_card, bg="surface")
        controls.pack(fill="x", padx=16, pady=14)

        # Start defaults to ~90 days ago, end to today, both as YYYY-MM-DD.
        today = datetime.date.today()
        start_default = today - datetime.timedelta(days=DEFAULT_PL_DAYS)

        start_row, self._pl_start = theme.field_row(controls, "Start date (YYYY-MM-DD)")
        start_row.pack(side="left", padx=(0, 12))
        self._pl_start.insert(0, start_default.isoformat())

        end_row, self._pl_end = theme.field_row(controls, "End date (YYYY-MM-DD)")
        end_row.pack(side="left", padx=(0, 12))
        self._pl_end.insert(0, today.isoformat())

        # The run button sits alongside the inputs, nudged down to line up with
        # the entries (the field_row caption pushes the entries down a little).
        run = theme.button(controls, "Run report", command=self._run_profit_loss,
                           kind="primary")
        run.pack(side="left", anchor="s", pady=(0, 1))

        # --- Results area, redrawn each time the report is run ----------------
        self._pl_results = theme.frame(self.content, bg="bg")
        self._pl_results.pack(fill="both", expand=True, pady=(16, 0))

        # Run once on first draw using the default range so results show
        # immediately rather than leaving the area empty.
        self._run_profit_loss()

    def _run_profit_loss(self):
        """Validate the two dates, then query sales in range and redraw the
        summary block and the per-medicine breakdown."""
        # Parse and validate both dates. strptime raises ValueError on a badly
        # formatted string, which we turn into a friendly error dialog.
        try:
            start = datetime.datetime.strptime(
                self._pl_start.get().strip(), "%Y-%m-%d").date()
            end = datetime.datetime.strptime(
                self._pl_end.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror(
                "Invalid date",
                "Please enter both dates as YYYY-MM-DD (for example 2026-01-31).",
            )
            return
        # A range that runs backwards makes no sense, so reject it.
        if start > end:
            messagebox.showerror(
                "Invalid range",
                "The start date must be on or before the end date.",
            )
            return

        # Clear any previous results before redrawing.
        for child in self._pl_results.winfo_children():
            child.destroy()

        # --- Headline figures for the whole range -----------------------------
        # revenue is the sum of sale totals; cost of goods uses the unit_cost
        # captured at sale time; profit is the difference. COALESCE keeps the
        # figures at 0 when no sales fall in the range.
        summary = self.db.fetch_one(
            "SELECT "
            "  COALESCE(SUM(total), 0) AS revenue, "
            "  COALESCE(SUM(quantity * unit_cost), 0) AS cost, "
            "  COALESCE(SUM(quantity), 0) AS units, "
            "  COUNT(*) AS num_sales "
            "FROM sales WHERE sale_date BETWEEN %s AND %s",
            (start, end),
        )
        revenue = float(summary["revenue"] or 0)
        cost = float(summary["cost"] or 0)
        profit = revenue - cost
        units = int(summary["units"] or 0)
        num_sales = int(summary["num_sales"] or 0)

        # Net profit is coloured green when positive, red when a loss, so the
        # bottom line is unmistakable at a glance.
        profit_fg = "primary" if profit >= 0 else "danger"

        # A row of metric cards mirroring the dashboard's summary style.
        cards = theme.frame(self._pl_results, bg="bg")
        cards.pack(fill="x")
        self._metric_card(cards, self._money(revenue), "Revenue")
        self._metric_card(cards, self._money(cost), "Cost of goods")
        self._metric_card(cards, self._money(profit), "Net profit", value_fg=profit_fg)
        self._metric_card(cards, str(units), "Units sold")
        self._metric_card(cards, str(num_sales), "Number of sales")

        # --- Per-medicine breakdown ------------------------------------------
        theme.label(
            self._pl_results,
            "Breakdown by medicine",
            kind="heading", fg="text", bg="bg",
        ).pack(anchor="w", pady=(18, 8))

        columns = ("medicine", "units", "revenue", "cost", "profit")
        headings = {
            "medicine": "Medicine", "units": "Units",
            "revenue": "Revenue", "cost": "Cost", "profit": "Profit",
        }
        right_aligned = {"units", "revenue", "cost", "profit"}
        tree = self._make_table(self._pl_results, columns, headings,
                                right_aligned, height=8)

        # Group sales by medicine within the range. LEFT JOIN medicines so a sale
        # whose medicine was later deleted (medicine_id set NULL) still appears.
        breakdown = self.db.fetch_all(
            "SELECT m.name AS name, "
            "  COALESCE(SUM(s.quantity), 0) AS units, "
            "  COALESCE(SUM(s.total), 0) AS revenue, "
            "  COALESCE(SUM(s.quantity * s.unit_cost), 0) AS cost "
            "FROM sales s "
            "LEFT JOIN medicines m ON m.medicine_id = s.medicine_id "
            "WHERE s.sale_date BETWEEN %s AND %s "
            "GROUP BY s.medicine_id, m.name "
            "ORDER BY revenue DESC",
            (start, end),
        )

        if not breakdown:
            # Nothing sold in range: show a placeholder rather than an empty grid.
            tree.insert("", "end", values=("No sales in this range", "", "", "", ""))
            return

        for row in breakdown:
            line_revenue = float(row["revenue"] or 0)
            line_cost = float(row["cost"] or 0)
            tree.insert(
                "", "end",
                values=(
                    row["name"] or "- (deleted medicine)",
                    int(row["units"] or 0),
                    self._money(line_revenue),
                    self._money(line_cost),
                    self._money(line_revenue - line_cost),
                ),
            )

    def _metric_card(self, parent, value, caption, value_fg="primary"):
        """Build one metric card: a large coloured number above a small muted
        caption, packed so the cards expand evenly across the row. value_fg lets
        the profit card flip to danger red when the business is at a loss."""
        card = theme.card(parent)
        card.pack(side="left", fill="both", expand=True, padx=6)
        inner = theme.frame(card, bg="surface")
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        theme.label(inner, value, kind="title", fg=value_fg,
                    bg="surface").pack(anchor="w")
        theme.label(inner, caption, kind="small", fg="muted",
                    bg="surface").pack(anchor="w", pady=(4, 0))

    # =========================================================== 3. stock value
    def _build_stock_by_supplier(self):
        """Show one row per supplier with the number of distinct medicines, the
        total units held, and the stock's worth at cost and at sale price. A
        TOTAL row sums every column."""
        theme.label(
            self.content,
            "Current stock grouped by supplier, valued at cost and at sale price.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(0, 10))

        columns = ("supplier", "medicines", "units", "cost_value", "sale_value")
        headings = {
            "supplier": "Supplier", "medicines": "Medicines",
            "units": "Total units", "cost_value": "Stock value at cost",
            "sale_value": "Potential sale value",
        }
        right_aligned = {"medicines", "units", "cost_value", "sale_value"}
        tree = self._make_table(self.content, columns, headings, right_aligned)

        # LEFT JOIN suppliers from the medicines side so that any medicine with a
        # NULL supplier_id falls into a single "- (no supplier)" bucket, while
        # suppliers with stock are named. COALESCE on the name labels that bucket.
        rows = self.db.fetch_all(
            "SELECT COALESCE(s.name, '- (no supplier)') AS supplier, "
            "  COUNT(DISTINCT m.medicine_id) AS medicines, "
            "  COALESCE(SUM(m.quantity), 0) AS units, "
            "  COALESCE(SUM(m.quantity * m.cost_price), 0) AS cost_value, "
            "  COALESCE(SUM(m.quantity * m.sale_price), 0) AS sale_value "
            "FROM medicines m "
            "LEFT JOIN suppliers s ON s.supplier_id = m.supplier_id "
            "GROUP BY supplier "
            "ORDER BY supplier ASC"
        )

        # Running totals for the summary row at the bottom.
        total_medicines = 0
        total_units = 0
        total_cost = 0.0
        total_sale = 0.0
        for row in rows:
            medicines = int(row["medicines"] or 0)
            units = int(row["units"] or 0)
            cost_value = float(row["cost_value"] or 0)
            sale_value = float(row["sale_value"] or 0)
            total_medicines += medicines
            total_units += units
            total_cost += cost_value
            total_sale += sale_value
            tree.insert(
                "", "end",
                values=(
                    row["supplier"],
                    medicines,
                    units,
                    self._money(cost_value),
                    self._money(sale_value),
                ),
            )

        # Grand total row, styled in the brand green.
        tree.insert(
            "", "end",
            values=(
                "TOTAL",
                total_medicines,
                total_units,
                self._money(total_cost),
                self._money(total_sale),
            ),
            tags=("total",),
        )
