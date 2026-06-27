"""The application shell: the top-level window, the login gate and the sidebar
navigation that swaps between the feature screens.

Flow: the window starts by showing the LoginView. Once the user authenticates
the login screen is destroyed and the main workspace (a sidebar + a content
area) is built. Clicking a sidebar item raises the matching view to the front
and refreshes its data. Keeping all of this in one place means each individual
view only has to worry about its own screen, not navigation.
"""

import tkinter as tk

from greenline import config
from greenline import theme
from greenline.ui.login_view import LoginView
from greenline.ui.dashboard_view import DashboardView
from greenline.ui.medicines_view import MedicinesView
from greenline.ui.sales_view import SalesView
from greenline.ui.clinics_view import ClinicsView
from greenline.ui.reports_view import ReportsView
from greenline.ui.charts_view import ChartsView


class MainWindow(tk.Tk):
    """The root Tk window. Subclassing Tk lets us treat the whole application as
    one object that owns the database handle and the current user."""

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_user = None          # filled in once login succeeds
        self._views = {}                  # nav key -> view instance cache
        self._nav_buttons = {}            # nav key -> sidebar button (for active state)

        # Basic window chrome: title, size and the dark background so there is
        # no white flash before content is drawn.
        self.title(config.APP_NAME)
        self.configure(bg=theme.color("bg"))
        self.geometry("1180x720")
        self.minsize(1040, 640)

        # ttk styling (tables, comboboxes) must be set up after the root exists.
        theme.init_ttk_styles(self)

        # Start at the login gate; the rest of the UI is built only after auth.
        self._show_login()

    # ------------------------------------------------------------------ login
    def _show_login(self):
        """Display the login screen, filling the whole window."""
        self._login = LoginView(self, self.db, on_success=self._on_login_success)
        self._login.pack(fill="both", expand=True)

    def _on_login_success(self, user):
        """Callback handed to LoginView; runs when credentials are accepted."""
        self.current_user = user
        self._login.destroy()             # remove the login screen entirely
        self._build_workspace()

    # -------------------------------------------------------------- workspace
    def _build_workspace(self):
        """Construct the post-login layout: a fixed sidebar on the left and a
        flexible content area on the right."""
        # Sidebar rail.
        self.sidebar = theme.frame(self, bg="sidebar", width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)   # keep its fixed width

        # Brand block at the top of the sidebar.
        brand = theme.frame(self.sidebar, bg="sidebar")
        brand.pack(fill="x", pady=(22, 18), padx=18)
        theme.label(brand, "Greenline", kind="brand", fg="primary",
                    bg="sidebar").pack(anchor="w")
        theme.label(brand, "Pharmacy", kind="small", fg="muted",
                    bg="sidebar").pack(anchor="w")

        # Content area where views are shown.
        self.content = theme.frame(self, bg="bg")
        self.content.pack(side="left", fill="both", expand=True)

        # Define the navigation items: (key, caption, view class). Order here is
        # the order they appear in the sidebar.
        self._nav_items = [
            ("dashboard", "Dashboard", DashboardView),
            ("medicines", "Medicines & Stock", MedicinesView),
            ("sales", "Record a Sale", SalesView),
            ("clinics", "Clinics & Credit", ClinicsView),
            ("reports", "Reports", ReportsView),
            ("charts", "Charts", ChartsView),
        ]
        for key, caption, _cls in self._nav_items:
            self._add_nav_button(key, caption)

        # A footer showing who is logged in plus a logout action.
        footer = theme.frame(self.sidebar, bg="sidebar")
        footer.pack(side="bottom", fill="x", padx=14, pady=14)
        who = self.current_user.get("full_name") or self.current_user["username"]
        theme.label(footer, "Signed in as", kind="small", fg="muted",
                    bg="sidebar").pack(anchor="w")
        theme.label(footer, who, kind="body_bold", fg="text",
                    bg="sidebar").pack(anchor="w", pady=(0, 8))
        theme.button(footer, "Log out", command=self._logout,
                     kind="ghost").pack(fill="x")

        # Show the first screen by default.
        self._select("dashboard")

    def _add_nav_button(self, key, caption):
        """Create one clickable sidebar entry that switches to its view.

        Each entry is a row made of a thin accent bar on the left (shown only
        for the active screen) plus a label. It is built from a Frame + Label
        rather than a tk.Button because macOS will not colour native buttons,
        and this also lets us draw the green active-state accent ourselves."""
        row = tk.Frame(self.sidebar, bg=theme.color("sidebar"))
        row.pack(fill="x", pady=1)
        # The 3px accent strip. It is sidebar-coloured (invisible) until this
        # item becomes the active screen, when _select turns it brand green.
        accent = tk.Frame(row, bg=theme.color("sidebar"), width=3)
        accent.pack(side="left", fill="y")
        lbl = tk.Label(
            row, text=caption, anchor="w", font=theme.font("nav"),
            fg=theme.color("muted"), bg=theme.color("sidebar"),
            padx=14, pady=11, cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True)

        # Clicking anywhere on the row (bar or label) selects the screen.
        for widget in (row, accent, lbl):
            widget.bind("<Button-1>", lambda _e, k=key: self._select(k))

        # Hover feedback, but only for items that are not the current screen so
        # the active highlight is never disturbed.
        def on_enter(_e):
            if key != getattr(self, "_active_key", None):
                lbl.config(bg=theme.color("surface"), fg=theme.color("text"))
                row.config(bg=theme.color("surface"))
        def on_leave(_e):
            if key != getattr(self, "_active_key", None):
                lbl.config(bg=theme.color("sidebar"), fg=theme.color("muted"))
                row.config(bg=theme.color("sidebar"))
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)

        # Store the three pieces so _select can recolour them later.
        self._nav_buttons[key] = (row, accent, lbl)

    def _select(self, key):
        """Raise the chosen view, creating it on first use, and update which
        sidebar button looks 'active'."""
        # Hide whatever view is currently shown.
        for view in self._views.values():
            view.pack_forget()

        # Lazily build the view the first time it is opened.
        if key not in self._views:
            view_cls = dict((k, c) for k, _cap, c in self._nav_items)[key]
            self._views[key] = view_cls(self.content, self.db)

        view = self._views[key]
        view.pack(fill="both", expand=True)
        # If the view exposes refresh(), pull fresh data each time it is shown
        # so edits made on other screens are reflected immediately.
        if hasattr(view, "refresh"):
            view.refresh()

        # Remember which screen is active (used by the hover handlers) and
        # recolour every sidebar row so only the active one is highlighted: a
        # green accent bar, a raised background and bright bold-looking text.
        self._active_key = key
        for k, (row, accent, lbl) in self._nav_buttons.items():
            if k == key:
                accent.config(bg=theme.color("primary"))
                row.config(bg=theme.color("surface"))
                lbl.config(bg=theme.color("surface"), fg=theme.color("text"))
            else:
                accent.config(bg=theme.color("sidebar"))
                row.config(bg=theme.color("sidebar"))
                lbl.config(bg=theme.color("sidebar"), fg=theme.color("muted"))

    def _logout(self):
        """Tear the workspace down and return to the login screen."""
        self.sidebar.destroy()
        self.content.destroy()
        self._views.clear()
        self._nav_buttons.clear()
        self.current_user = None
        self._show_login()
