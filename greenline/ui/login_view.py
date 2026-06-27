"""The login screen for Greenline Pharmacy.

This is the first thing the user sees. The client explicitly asked for password
protection (Criteria A, Appendix 1 point 7), so no other view is reachable until
a valid username and password have been entered. The screen is deliberately
simple: a single centred card on the dark theme background with two fields and
one obvious button, because the client is not confident with computers.

All credential checking is delegated to greenline.auth (which compares against
the salted PBKDF2 hashes in the database); this view only collects input,
validates that it is not blank, shows clear inline error messages, and reports a
successful login back to the application through the on_success callback.
"""

import tkinter as tk

from greenline import config
from greenline import auth
from greenline import theme


class LoginView(tk.Frame):
    """The full-window login screen.

    The host application creates one of these, gives it a database handle and an
    on_success(user) callback, and packs it into the main window. When the user
    signs in successfully the callback fires with the authenticated user dict so
    the application can swap this screen out for the main dashboard.
    """

    def __init__(self, parent, db, on_success):
        # Paint our own background so the screen fills the window with the deep
        # forest-green canvas defined by the theme.
        super().__init__(parent, bg=theme.color("bg"))

        # Store the collaborators we were handed: the database (for the auth
        # lookup) and the callback to run once the login succeeds.
        self.db = db
        self.on_success = on_success

        # Build the visible widgets.
        self._build_ui()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        """Construct the centred login card and everything inside it."""
        # The card is the raised panel holding the whole form. place() with
        # relx/rely 0.5 and anchor "center" pins it to the exact middle of the
        # window regardless of how the window is resized.
        card = theme.card(self)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # An inner padding frame keeps the contents off the card's edges. It
        # sits on the surface colour so the labels packed onto it blend in.
        inner = theme.frame(card, bg="surface")
        inner.pack(padx=36, pady=32)

        # --- Branding ---------------------------------------------------
        # The application name in big brand-green type, with the tagline in
        # muted grey beneath it, gives the screen a clear identity.
        theme.label(inner, config.APP_NAME, kind="brand",
                    fg="primary", bg="surface").pack(anchor="w")
        theme.label(inner, config.APP_TAGLINE, kind="small",
                    fg="muted", bg="surface").pack(anchor="w", pady=(2, 22))

        # --- Input fields ----------------------------------------------
        # field_row builds a captioned, pre-styled entry and returns the entry
        # widget so we can read its contents later. Both sit on the card so we
        # keep references to the entries on self.
        user_row, self.username_entry = theme.field_row(inner, "Username")
        user_row.pack(fill="x", pady=(0, 12))

        pass_row, self.password_entry = theme.field_row(inner, "Password")
        # show="*" masks the password as it is typed; field_row's entry does not
        # set that, so configure it here.
        self.password_entry.config(show="*")
        pass_row.pack(fill="x", pady=(0, 8))

        # --- Inline error message --------------------------------------
        # A normally-empty danger-coloured label that we fill in when validation
        # fails or the credentials are rejected. It is created up front (rather
        # than created/destroyed each time) so the layout never jumps around.
        self.error_label = theme.label(inner, "", kind="small",
                                       fg="danger", bg="surface")
        self.error_label.pack(anchor="w", pady=(0, 8))

        # --- Sign in button --------------------------------------------
        # The primary green button is the obvious call to action. It fills the
        # width of the card so it is a large, easy target to click.
        sign_in = theme.button(inner, "Sign in", command=self._attempt_login,
                               kind="primary")
        sign_in.pack(fill="x", pady=(0, 16))

        # --- Demo hint --------------------------------------------------
        # A quiet reminder of the seeded demo account so the client (and the
        # examiner) can always get in without guessing.
        theme.label(inner, "Demo login -  username: admin   password: admin123",
                    kind="small", fg="muted", bg="surface").pack(anchor="w")

        # --- Keyboard convenience --------------------------------------
        # Pressing Enter in either field submits the form, so the user never has
        # to reach for the mouse. Binding on both entries covers wherever the
        # focus happens to be.
        self.username_entry.bind("<Return>", self._on_return)
        self.password_entry.bind("<Return>", self._on_return)

        # Start with the cursor already in the username field for immediate
        # typing on launch.
        self.username_entry.focus_set()

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------
    def _on_return(self, _event):
        """Enter-key handler. Delegates to the same logic as the button."""
        self._attempt_login()

    def _attempt_login(self):
        """Validate the input, check it against the database and either report
        an error inline or hand the authenticated user back to the application."""
        # Read the two fields, trimming surrounding whitespace so a stray space
        # is not mistaken for a real value.
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        # Validation (Criteria A point 6): refuse blank input before touching the
        # database, and tell the user exactly what is wrong.
        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        # Ask the auth module to verify the credentials. It returns the user row
        # dict on success or None on failure.
        user = auth.authenticate(self.db, username, password)

        if user is None:
            # Wrong username or password: show the error and clear the password
            # field so the user can retype it cleanly (the username is kept).
            self._show_error("Invalid username or password.")
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus_set()
            return

        # Success: clear any lingering error and notify the application, which
        # will replace this screen with the main dashboard.
        self.error_label.config(text="")
        self.on_success(user)

    def _show_error(self, message):
        """Display an inline error message in the danger colour."""
        self.error_label.config(text=message)
