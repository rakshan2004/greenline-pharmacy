"""The charts screen: turning raw sales and stock figures into pictures.

The client asked for the data to be summarised visually so trends can be read
at a glance rather than scanned out of a table (Criteria A: "Sales and stock
data can be displayed in chart format (pie charts, bar charts) to facilitate
quick analysis"). This view embeds matplotlib directly inside the Tkinter window
so the charts share the same dark Greenline look as the rest of the application.

A small selector at the top lets the client pick which of four reports to see;
each one is a single aggregate query drawn onto one shared matplotlib Figure.
Everything is plotted in refresh()/_draw rather than __init__ so re-opening the
screen always reflects the latest data entered elsewhere.
"""

import tkinter as tk

# matplotlib is configured for embedding rather than its own pop-up windows.
# "Agg" sets a non-interactive base renderer; the Tk canvas below is what
# actually drives drawing, and we deliberately avoid pyplot so no stray figure
# windows are ever created.
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from greenline import theme


# A rotating palette of greens and theme accents used for the multi-slice pie
# charts. Drawn from the design system first, then topped up with a few extra
# hand-picked green hexes so charts with many categories never run out of
# distinct colours.
SLICE_COLORS = [
    theme.color("primary"),
    theme.color("amber"),
    theme.color("info"),
    theme.color("danger"),
    theme.color("primary_dark"),
    "#7FD89C",   # light mint
    "#3E9D6B",   # mid green
    "#9CE0B4",   # pale green
    "#16624A",   # deep teal-green
]


class ChartsView(tk.Frame):
    """The charts screen. The page header, selector and matplotlib canvas are
    built once in __init__; switching the selector or calling refresh() simply
    re-runs the relevant query and redraws onto the same Figure."""

    # (label, drawing-method-name) pairs. The labels populate the selector and
    # the names map to the private _draw_* methods that do the plotting.
    CHART_OPTIONS = [
        ("Stock units by supplier", "_draw_stock_by_supplier"),
        ("Sales revenue by medicine", "_draw_sales_by_medicine"),
        ("Monthly sales revenue", "_draw_monthly_revenue"),
        ("Receivables by clinic", "_draw_receivables_by_clinic"),
    ]

    def __init__(self, parent, db):
        super().__init__(parent, bg=theme.color("bg"))
        self.db = db

        # Outer padding so the content does not touch the window edges.
        outer = theme.frame(self, bg="bg")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        # --- Page header (static) ---------------------------------------------
        header = theme.frame(outer, bg="bg")
        header.pack(fill="x", anchor="w")
        theme.heading(header, "Charts", bg="bg").pack(anchor="w")
        theme.label(
            header,
            "Visual summaries of your stock, sales and receivables.",
            kind="small", fg="muted", bg="bg",
        ).pack(anchor="w", pady=(2, 0))

        # --- Chart selector ----------------------------------------------------
        # A read-only dropdown of the available reports. Choosing one fires
        # _on_select which redraws the canvas below.
        selector_row = theme.frame(outer, bg="bg")
        selector_row.pack(fill="x", pady=(18, 0))
        theme.label(selector_row, "Chart:", kind="small", fg="muted",
                    bg="bg").pack(side="left", padx=(0, 8))
        self.selector = theme.combobox(
            selector_row, [label for label, _ in self.CHART_OPTIONS], width=28
        )
        self.selector.current(0)               # default to the first report
        self.selector.pack(side="left")
        self.selector.bind("<<ComboboxSelected>>", self._on_select)

        # --- Matplotlib figure + Tk canvas ------------------------------------
        # A single Figure is reused for every report: each redraw clears it and
        # adds a fresh subplot. The whole figure is tinted to the surface colour
        # so it blends into the dark theme instead of showing a white rectangle.
        self.figure = Figure(figsize=(8, 4.5), dpi=100)
        self.figure.patch.set_facecolor(theme.color("surface"))

        canvas_holder = theme.card(outer)
        canvas_holder.pack(fill="both", expand=True, pady=(16, 0))
        self.canvas = FigureCanvasTkAgg(self.figure, master=canvas_holder)
        self.canvas.get_tk_widget().pack(fill="both", expand=True,
                                         padx=8, pady=8)

        # Draw the default chart straight away so the screen is never blank.
        self._draw()

    # ------------------------------------------------------------------ helpers
    def _on_select(self, _event=None):
        """Combobox callback: redraw whichever report the client just picked."""
        self._draw()

    def refresh(self):
        """Re-query and redraw the currently selected chart. Called by the
        navigation shell each time the charts screen is shown so the picture
        always reflects edits made on the other views."""
        self._draw()

    def _draw(self):
        """Clear the shared figure, add one subplot, style it, and dispatch to
        the drawing method for the currently selected report."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        self._style_axes(ax)

        # Look up the drawing method that matches the selected option label.
        index = self.selector.current()
        _, method_name = self.CHART_OPTIONS[index]
        getattr(self, method_name)(ax)

        # tight_layout keeps labels from being clipped at the figure edges.
        self.figure.tight_layout()
        self.canvas.draw()

    def _style_axes(self, ax):
        """Apply the shared dark-theme styling to an axes: surface background,
        light tick labels and bordered spines. Per-chart titles/labels are set
        by the individual drawing methods on top of this."""
        ax.set_facecolor(theme.color("surface"))
        # Tick labels in muted text so the data, not the scaffolding, stands out.
        ax.tick_params(colors=theme.color("muted"), labelsize=9)
        # Thin bordered spines matching the rest of the UI outlines.
        for spine in ax.spines.values():
            spine.set_color(theme.color("border"))

    def _empty_message(self, ax):
        """Draw a centred "No data to display" note instead of an empty chart.
        Used whenever a query returns no rows so the screen never crashes or
        shows a confusing blank frame."""
        ax.text(
            0.5, 0.5, "No data to display",
            ha="center", va="center", transform=ax.transAxes,
            color=theme.color("muted"), fontsize=13,
        )
        # Hide the axis furniture; there is nothing to measure against.
        ax.set_xticks([])
        ax.set_yticks([])

    def _title(self, ax, text):
        """Set a chart title in the brand green for a consistent heading look."""
        ax.set_title(text, color=theme.color("primary"), fontsize=13, pad=12)

    # --------------------------------------------------------------- pie: stock
    def _draw_stock_by_supplier(self, ax):
        """PIE - total stock units held, grouped by supplier. A LEFT JOIN keeps
        medicines whose supplier was deleted (supplier_id NULL); those are
        bucketed under "Unassigned" via COALESCE."""
        rows = self.db.fetch_all(
            "SELECT COALESCE(s.name, 'Unassigned') AS label, "
            "SUM(m.quantity) AS total "
            "FROM medicines m "
            "LEFT JOIN suppliers s ON m.supplier_id = s.supplier_id "
            "GROUP BY label "
            "HAVING total > 0 "
            "ORDER BY total DESC"
        )

        if not rows:
            self._empty_message(ax)
            return

        labels = [r["label"] for r in rows]
        values = [int(r["total"]) for r in rows]
        self._pie(ax, labels, values)
        self._title(ax, "Stock units by supplier")

    # ------------------------------------------------------------- pie: revenue
    def _draw_sales_by_medicine(self, ax):
        """PIE - sales revenue grouped by medicine. To keep the chart readable
        only the top six earners are shown individually; everything else is
        summed into a single "Other" slice."""
        rows = self.db.fetch_all(
            "SELECT COALESCE(m.name, 'Unknown') AS label, "
            "SUM(sa.total) AS revenue "
            "FROM sales sa "
            "LEFT JOIN medicines m ON sa.medicine_id = m.medicine_id "
            "GROUP BY label "
            "ORDER BY revenue DESC"
        )

        if not rows:
            self._empty_message(ax)
            return

        # Split into the leading six and an aggregated remainder.
        top = rows[:6]
        labels = [r["label"] for r in top]
        values = [float(r["revenue"]) for r in top]
        other = sum(float(r["revenue"]) for r in rows[6:])
        if other > 0:
            labels.append("Other")
            values.append(other)

        self._pie(ax, labels, values)
        self._title(ax, "Sales revenue by medicine")

    # ------------------------------------------------------------- bar: monthly
    def _draw_monthly_revenue(self, ax):
        """BAR - total sales revenue per calendar month. DATE_FORMAT collapses
        each sale_date to a YYYY-MM bucket directly in SQL so the bars line up
        in chronological order."""
        rows = self.db.fetch_all(
            "SELECT DATE_FORMAT(sale_date, '%Y-%m') AS month, "
            "SUM(total) AS revenue "
            "FROM sales "
            "GROUP BY month "
            "ORDER BY month ASC"
        )

        if not rows:
            self._empty_message(ax)
            return

        months = [r["month"] for r in rows]
        values = [float(r["revenue"]) for r in rows]

        # All bars in the brand green for the headline sales report.
        ax.bar(months, values, color=theme.color("primary"))
        self._title(ax, "Monthly sales revenue")
        ax.set_ylabel("Revenue (Rs)", color=theme.color("muted"), fontsize=10)
        # Slant the month labels so longer runs of months do not overlap.
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha("right")

    # --------------------------------------------------------- bar: receivables
    def _draw_receivables_by_clinic(self, ax):
        """BAR - the outstanding balance owed by each clinic. A charge increases
        the balance and a payment decreases it, so the balance is the signed sum
        of the ledger (charges minus payments) per clinic."""
        rows = self.db.fetch_all(
            "SELECT c.name AS label, "
            "SUM(CASE WHEN t.txn_type='charge' THEN t.amount "
            "ELSE -t.amount END) AS balance "
            "FROM clinics c "
            "LEFT JOIN clinic_transactions t ON c.clinic_id = t.clinic_id "
            "GROUP BY c.clinic_id, c.name "
            "ORDER BY balance DESC"
        )

        # Drop clinics whose balance is missing or zero so the chart only shows
        # clinics that actually owe money.
        rows = [r for r in rows if r["balance"] is not None
                and float(r["balance"]) != 0]

        if not rows:
            self._empty_message(ax)
            return

        labels = [r["label"] for r in rows]
        values = [float(r["balance"]) for r in rows]

        # Receivables are a warning-style figure, so colour the bars amber.
        ax.bar(labels, values, color=theme.color("amber"))
        self._title(ax, "Receivables by clinic")
        ax.set_ylabel("Owed (Rs)", color=theme.color("muted"), fontsize=10)
        for label in ax.get_xticklabels():
            label.set_rotation(20)
            label.set_ha("right")

    # ----------------------------------------------------------- pie shared draw
    def _pie(self, ax, labels, values):
        """Shared pie-drawing helper: plot the slices with the rotating theme
        palette and label each wedge with its name and percentage in light text
        so it reads clearly on the dark surface."""
        # Cycle the palette so charts with more categories than colours still
        # get a colour for every slice.
        colors = [SLICE_COLORS[i % len(SLICE_COLORS)] for i in range(len(values))]
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"fontsize": 9},
        )
        # Slice name labels in muted text; the inner percentage labels in the
        # dark background colour so they sit legibly on the bright wedges.
        for text in texts:
            text.set_color(theme.color("muted"))
        for autotext in autotexts:
            autotext.set_color(theme.color("bg"))
            autotext.set_fontsize(8)
        ax.axis("equal")   # keep the pie circular rather than an ellipse
