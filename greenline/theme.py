"""The visual identity ("look and feel") of Greenline Pharmacy.

Tkinter's default widgets are flat grey 1990s-style controls. The client wanted
something that feels modern and pleasant to use, so this module defines a single
custom design language and a set of factory functions that build pre-styled
widgets. Every view imports these helpers instead of creating raw Tk widgets,
which guarantees the whole application shares one consistent, distinctive look:
a deep forest-green canvas, a near-black sidebar, a bright "greenline" accent
and an amber warning colour. Centralising the styling here also means the entire
theme can be re-skinned from one file.
"""

import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# Colour palette. Each colour has a named role rather than being used raw, so
# the intent ("surface", "danger") is obvious at every call site.
# ---------------------------------------------------------------------------
PALETTE = {
    "bg":           "#0F1714",  # main window background (deep slate-green charcoal)
    "surface":      "#172019",  # raised cards / panels sit on top of the bg
    "surface_alt":  "#212C24",  # alternating rows, hovered panels, ghost buttons
    "sidebar":      "#0B1310",  # navigation rail, darkest tone
    "primary":      "#36C77D",  # Greenline brand green, the main accent
    "primary_dark": "#269A5E",  # pressed/active state of green buttons
    "amber":        "#F2B441",  # warnings: expiring stock, low stock
    "danger":       "#F0555C",  # destructive actions and errors
    "info":         "#5AA9FF",  # neutral informational accent
    "text":         "#EBF2EC",  # primary readable text on dark backgrounds
    "muted":        "#8DA597",  # secondary / hint text
    "border":       "#26342B",  # thin separators and input outlines
    "field":        "#101A14",  # input field background
}

# ---------------------------------------------------------------------------
# Typography. A small named scale keeps headings and body text consistent.
# Helvetica Neue is a clean sans-serif present on macOS; Tk falls back grace-
# fully if it is unavailable.
# ---------------------------------------------------------------------------
FONTS = {
    "brand":   ("Helvetica Neue", 20, "bold"),
    "title":   ("Helvetica Neue", 22, "bold"),
    "heading": ("Helvetica Neue", 15, "bold"),
    "body":    ("Helvetica Neue", 12),
    "body_bold": ("Helvetica Neue", 12, "bold"),
    "small":   ("Helvetica Neue", 10),
    "nav":     ("Helvetica Neue", 13),
    "mono":    ("Menlo", 11),
}


def color(name):
    """Look up a palette colour by role name (small helper for readability)."""
    return PALETTE[name]


def font(name):
    """Look up a font tuple by role name."""
    return FONTS[name]


# ---------------------------------------------------------------------------
# Widget factories. These return ordinary Tk widgets that have already been
# given the Greenline styling, so views simply call theme.button(...) etc.
# ---------------------------------------------------------------------------

def frame(parent, bg="bg", **kwargs):
    """A plain container frame painted with one of the palette backgrounds."""
    return tk.Frame(parent, bg=PALETTE[bg], **kwargs)


def card(parent, **kwargs):
    """A raised panel ("card") used to group related controls. The subtle
    highlight border gives it depth against the darker background."""
    return tk.Frame(
        parent,
        bg=PALETTE["surface"],
        highlightbackground=PALETTE["border"],
        highlightthickness=1,
        bd=0,
        **kwargs,
    )


def label(parent, text, kind="body", fg="text", bg="bg", **kwargs):
    """A text label. "kind" picks the font from the scale; "fg"/"bg" pick
    palette colours so labels read correctly on whatever surface they sit on."""
    return tk.Label(
        parent,
        text=text,
        font=FONTS[kind],
        fg=PALETTE[fg],
        bg=PALETTE[bg],
        **kwargs,
    )


def heading(parent, text, bg="bg", **kwargs):
    """A section heading in the brand green for clear visual hierarchy."""
    return label(parent, text, kind="heading", fg="primary", bg=bg, **kwargs)


def button(parent, text, command=None, kind="primary", width=None, **kwargs):
    """A flat, modern button.

    IMPORTANT macOS detail: the classic tk.Button widget ignores background
    colours on macOS because the native Aqua control paints itself, so coloured
    buttons render as blank white blocks. To get a consistent, fully styleable
    button on every platform we build it out of a tk.Label instead (labels do
    honour bg/fg everywhere) and wire up the click, hover and press behaviour by
    hand. The result looks identical on macOS, Windows and Linux.

    "kind" picks the colour scheme: primary (solid green), amber, danger (red)
    or ghost (a subtle outlined button for secondary actions).
    """
    # (resting bg, hover bg, text colour) for each button kind.
    fills = {
        "primary": (PALETTE["primary"], PALETTE["primary_dark"], "#08130C"),
        "amber":   (PALETTE["amber"], "#D89A2E", "#1A1303"),
        "danger":  (PALETTE["danger"], "#C8444A", "#FFFFFF"),
        "ghost":   (PALETTE["surface_alt"], PALETTE["surface_alt"], PALETTE["text"]),
    }
    rest, hover, fg = fills.get(kind, fills["primary"])

    lbl = tk.Label(
        parent,
        text=text,
        font=FONTS["body_bold"],
        fg=fg,
        bg=rest,
        padx=18,
        pady=9,
        cursor="hand2",           # pointer cursor signals "clickable"
        **kwargs,
    )
    if width is not None:
        lbl.config(width=width)
    # A ghost button reads as a secondary action, so give it a thin outline
    # instead of a solid fill to set it apart from the primary green buttons.
    if kind == "ghost":
        lbl.config(highlightthickness=1, highlightbackground=PALETTE["border"])

    # Remember the resting/hover colours on the widget itself. Storing them as
    # attributes lets callers that re-skin a button (for example a selected tab
    # in the reports screen) update _rest/_hover so the hover handlers below
    # keep working with the new colours.
    lbl._rest = rest
    lbl._hover = hover

    # Hover: brighten to the hover colour; leave: fall back to the resting one.
    lbl.bind("<Enter>", lambda _e: lbl.config(bg=lbl._hover))
    lbl.bind("<Leave>", lambda _e: lbl.config(bg=lbl._rest))
    # Press feedback plus the actual click: fire the command on mouse release so
    # it behaves like a normal push button.
    lbl.bind("<ButtonPress-1>", lambda _e: lbl.config(bg=lbl._hover))
    if command is not None:
        lbl.bind("<ButtonRelease-1>", lambda _e: command())
    return lbl


def entry(parent, show=None, width=24, **kwargs):
    """A single-line text input styled to match (dark field, green caret)."""
    return tk.Entry(
        parent,
        show=show,                # show="*" turns it into a password field
        width=width,
        font=FONTS["body"],
        fg=PALETTE["text"],
        bg=PALETTE["field"],
        insertbackground=PALETTE["primary"],   # the text cursor colour
        relief="flat",
        highlightthickness=1,
        highlightbackground=PALETTE["border"],
        highlightcolor=PALETTE["primary"],     # outline turns green when focused
        **kwargs,
    )


def field_row(parent, caption):
    """Build a labelled input: a small caption above a styled entry, packed in
    their own frame. Returns (row_frame, entry_widget) so the caller can read
    the entry later. Used heavily by the add/edit forms."""
    row = frame(parent, bg="surface")
    label(row, caption, kind="small", fg="muted", bg="surface").pack(anchor="w")
    e = entry(row)
    e.pack(fill="x", pady=(2, 0))
    return row, e


class Dropdown(tk.Frame):
    """A custom dark dropdown ("combobox") for picking one value from a list.

    Why not ttk.Combobox: on macOS the native combobox ignores our colours (it
    renders as a grey Aqua control) and, in read-only mode, keeps the chosen
    text stuck in a selection highlight that the user cannot clear. This widget
    is built entirely from Tk Labels so it honours the theme everywhere, and it
    exposes the small slice of the ttk.Combobox API the views rely on
    (current(), get(), and the <<ComboboxSelected>> virtual event) so it is a
    drop-in replacement.
    """

    def __init__(self, parent, values, width=22):
        # The frame itself is the bordered "field" box.
        super().__init__(parent, bg=PALETTE["field"], highlightthickness=1,
                         highlightbackground=PALETTE["border"], cursor="hand2")
        self._values = list(values)                 # the selectable options
        self._index = 0 if self._values else -1     # which option is current
        self._popup = None                          # the open list window, if any
        self._root_bind = None                      # id of the outside-click handler
        self._listeners = []                        # <<ComboboxSelected>> callbacks

        # The chosen value, shown on the left and filling the available width.
        self._value = tk.Label(self, anchor="w", bg=PALETTE["field"],
                               fg=PALETTE["text"], font=FONTS["body"],
                               padx=10, pady=7, width=width)
        self._value.pack(side="left", fill="x", expand=True)
        # A small green caret on the right hints that this opens a list.
        self._caret = tk.Label(self, text="▾", bg=PALETTE["field"],
                               fg=PALETTE["primary"], font=FONTS["small"],
                               padx=10, pady=7)
        self._caret.pack(side="right")
        self._render_value()

        # Clicking any part of the box opens (or closes) the option list.
        for widget in (self, self._value, self._caret):
            widget.bind("<Button-1>", lambda _e: self._toggle())
        # Highlight the outline in green while the mouse is over the box.
        self.bind("<Enter>", lambda _e: self.config(highlightbackground=PALETTE["primary"]))
        self.bind("<Leave>", lambda _e: self.config(highlightbackground=PALETTE["border"]))

    # -- public API (mirrors the bits of ttk.Combobox the app uses) -----------
    def current(self, index=None):
        """With no argument, return the selected option's index. With an index,
        select that option (without firing the change event)."""
        if index is None:
            return self._index
        self._index = index
        self._render_value()

    def get(self):
        """Return the currently selected option's text (or '' if none)."""
        if 0 <= self._index < len(self._values):
            return self._values[self._index]
        return ""

    def bind(self, sequence=None, func=None, add=None):
        """Intercept binding of the selection event so we can notify listeners
        directly. Tk silently drops virtual events for windows that are not yet
        mapped, so instead of relying solely on event_generate we keep our own
        list of callbacks for <<ComboboxSelected>> and call them from _choose.
        Every other binding is passed straight through to the normal Tk machinery."""
        if sequence == "<<ComboboxSelected>>" and func is not None:
            self._listeners.append(func)
            return ""
        return super().bind(sequence, func, add)

    def set_values(self, values):
        """Replace the list of options, keeping a valid selection."""
        self._values = list(values)
        if self._index >= len(self._values):
            self._index = 0 if self._values else -1
        self._render_value()

    # -- internals ------------------------------------------------------------
    def _render_value(self):
        """Refresh the label so it shows the currently selected option."""
        self._value.config(text=self.get())

    def _toggle(self):
        """Open the list if closed, close it if already open."""
        if self._popup is not None:
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self):
        """Pop up a borderless window directly below the box listing every
        option as a clickable, hover-highlighted row."""
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2

        top = tk.Toplevel(self)
        top.wm_overrideredirect(True)            # no title bar, just the list
        top.configure(bg=PALETTE["border"])      # 1px border colour showing through
        top.attributes("-topmost", True)         # float above the main window
        inner = tk.Frame(top, bg=PALETTE["surface"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # Build one row per option.
        for i, value in enumerate(self._values):
            # The current selection is pre-highlighted in dark green.
            base = PALETTE["primary_dark"] if i == self._index else PALETTE["surface"]
            item = tk.Label(inner, text=value, anchor="w", bg=base,
                            fg=PALETTE["text"], font=FONTS["body"],
                            padx=10, pady=7, cursor="hand2")
            item.pack(fill="x")
            # Hover brightens the row; leaving restores its base colour.
            item.bind("<Enter>", lambda _e, it=item: it.config(bg=PALETTE["surface_alt"]))
            item.bind("<Leave>", lambda _e, it=item, b=base: it.config(bg=b))
            # Clicking a row selects it.
            item.bind("<Button-1>", lambda _e, idx=i: self._choose(idx))

        # Size the window to its contents and at least the width of the box.
        top.update_idletasks()
        width = max(self.winfo_width(), inner.winfo_reqwidth() + 2)
        height = inner.winfo_reqheight() + 2
        top.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self._popup = top

        # Close the list when the user clicks anywhere else in the application.
        root = self.winfo_toplevel()
        self._root_bind = root.bind("<Button-1>", self._on_outside_click, add="+")

    def _on_outside_click(self, event):
        """Close the popup unless the click landed inside it (clicks on the list
        rows are handled by their own binding, which also closes it)."""
        if self._popup is None:
            return
        # event.widget belonging to the popup window has a Tk path that starts
        # with the popup's path; ignore those so a row click is not double-handled.
        if str(event.widget).startswith(str(self._popup)):
            return
        self._close_popup()

    def _choose(self, index):
        """Apply the clicked option, close the list and notify any listeners by
        firing the same virtual event a ttk.Combobox would."""
        self._index = index
        self._render_value()
        self._close_popup()
        # Notify every registered listener directly (reliable even before the
        # window is mapped), and also fire the real virtual event for anything
        # bound through the normal Tk path.
        for callback in self._listeners:
            callback(None)
        self.event_generate("<<ComboboxSelected>>")

    def _close_popup(self):
        """Destroy the popup window and remove the outside-click handler."""
        if self._root_bind is not None:
            self.winfo_toplevel().unbind("<Button-1>", self._root_bind)
            self._root_bind = None
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None


def combobox(parent, values, width=22):
    """Factory used throughout the app: a dark, theme-matching dropdown for
    picking one value from a fixed list (e.g. choosing a supplier). Returns a
    Dropdown, our custom replacement for the native combobox."""
    return Dropdown(parent, values, width=width)


def init_ttk_styles(root):
    """Configure the ttk widgets that cannot be styled with simple options,
    namely the Treeview tables and the Combobox. Called once at start-up after
    the root window exists. Returns the ttk.Style object."""
    style = ttk.Style(root)
    style.theme_use("clam")   # "clam" is the most customisable built-in base

    # Table body: dark rows, light text, generous row height for an airy feel.
    style.configure(
        "Greenline.Treeview",
        background=PALETTE["surface"],
        fieldbackground=PALETTE["surface"],
        foreground=PALETTE["text"],
        rowheight=32,
        borderwidth=0,
        relief="flat",
        font=FONTS["body"],
    )
    # Remove the boxed border that "clam" draws around the whole table.
    style.layout("Greenline.Treeview",
                 [("Greenline.Treeview.treearea", {"sticky": "nswe"})])
    # Table header: a slightly raised strip with brand-green capitalised labels.
    style.configure(
        "Greenline.Treeview.Heading",
        background=PALETTE["surface_alt"],
        foreground=PALETTE["primary"],
        font=FONTS["body_bold"],
        relief="flat",
        padding=(10, 8),
    )
    # Keep the header flat (no sunken effect) when it is clicked.
    style.map("Greenline.Treeview.Heading",
              background=[("active", PALETTE["surface_alt"])])
    # Selected row uses the brand green so the current selection is obvious.
    style.map(
        "Greenline.Treeview",
        background=[("selected", PALETTE["primary_dark"])],
        foreground=[("selected", PALETTE["text"])],
    )
    # Combobox colours to match the dark fields.
    style.configure(
        "Greenline.TCombobox",
        fieldbackground=PALETTE["field"],
        background=PALETTE["surface_alt"],
        foreground=PALETTE["text"],
        arrowcolor=PALETTE["primary"],
        bordercolor=PALETTE["border"],
        relief="flat",
    )
    return style
