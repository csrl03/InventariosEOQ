"""
gui_utils.py — Constantes de estilos y helpers compartidos de GUI
=================================================================
Importar desde todos los módulos de pestañas para mantener coherencia visual.
"""

import tkinter as tk
from tkinter import ttk

# ─── Paleta de colores ────────────────────────────────────────────────────────

C = {
    "bg":       "#1a2a3a",
    "panel":    "#243447",
    "input_bg": "#2d3f52",
    "boton":    "#2980b9",
    "boton_h":  "#3498db",
    "verde":    "#27ae60",
    "texto":    "#ecf0f1",
    "dim":      "#95a5a6",
    "inv":      "#3498db",
    "ss":       "#e74c3c",
    "rop":      "#f39c12",
    "grid":     "#2c3e50",
    "graf_bg":  "#1a2a3a",
    "alerta":   "#e74c3c",
    "ok":       "#27ae60",
    "warn":     "#f39c12",
}

# ─── Fuentes ──────────────────────────────────────────────────────────────────

F_TITULO = ("Segoe UI", 13, "bold")
F_LABEL  = ("Segoe UI", 10)
F_BOLD   = ("Segoe UI", 10, "bold")
F_BOTON  = ("Segoe UI", 10, "bold")
F_MONO   = ("Consolas", 10)
F_SMALL  = ("Segoe UI", 9)
F_H2     = ("Segoe UI", 11, "bold")


# ─── Helper: fila label + entry ──────────────────────────────────────────────

def _entry_row(parent, texto, default, fila, col=0, ancho=18):
    """Crea label + entry en `fila` del grid de `parent`. Devuelve StringVar."""
    ttk.Label(parent, text=texto, style="In.TLabel").grid(
        row=fila, column=col, sticky="w", padx=(10, 4), pady=3
    )
    var = tk.StringVar(value=str(default))
    ttk.Entry(parent, textvariable=var, width=ancho, style="In.TEntry").grid(
        row=fila, column=col + 1, sticky="ew", padx=(0, 10), pady=3
    )
    return var


def _flt(var, nombre, minval=None):
    """Convierte StringVar/str a float con validación."""
    try:
        raw = var.get() if hasattr(var, "get") else str(var)
        v = float(raw.replace(",", "."))
    except ValueError:
        raise ValueError(f"'{nombre}' no es un número válido.")
    if minval is not None and v < minval:
        raise ValueError(f"'{nombre}' debe ser ≥ {minval}.")
    return v


def _int(var, nombre, minval=None):
    """Convierte StringVar/str a int con validación."""
    v = int(_flt(var, nombre, minval))
    return v


# ─── Helper: tabla Treeview estilizada ───────────────────────────────────────

def make_treeview(parent, columns, height=14):
    """
    Crea un ttk.Treeview con columnas y scrollbars listos para usar.
    Retorna (frame, treeview).
    """
    frm = ttk.Frame(parent)
    frm.rowconfigure(0, weight=1)
    frm.columnconfigure(0, weight=1)

    tv = ttk.Treeview(frm, columns=columns, show="headings",
                      style="Cal.Treeview", height=height)
    for c in columns:
        tv.heading(c, text=c)
        tv.column(c, width=110, anchor="center", minwidth=60)
    tv.grid(row=0, column=0, sticky="nsew")

    sb_v = ttk.Scrollbar(frm, orient="vertical", command=tv.yview)
    sb_v.grid(row=0, column=1, sticky="ns")
    tv.configure(yscrollcommand=sb_v.set)

    sb_h = ttk.Scrollbar(frm, orient="horizontal", command=tv.xview)
    sb_h.grid(row=1, column=0, sticky="ew")
    tv.configure(xscrollcommand=sb_h.set)

    return frm, tv


# ─── Tooltip flotante ─────────────────────────────────────────────────────────

class ToolTip:
    """
    Tooltip flotante que aparece al pasar el mouse sobre un widget.

    Uso:
        ToolTip(btn, "Abre el formulario para crear un nuevo registro.")
        tip(entry, "Ingrese la demanda anual en unidades.")
    """
    _DELAY  = 600      # ms antes de mostrar
    _BG     = "#1c2e3f"
    _FG     = "#ecf0f1"
    _BORDER = "#3498db"

    def __init__(self, widget: tk.Widget, text: str):
        self._widget  = widget
        self._text    = text
        self._job     = None
        self._tip_win = None
        widget.bind("<Enter>",       self._schedule, add="+")
        widget.bind("<Leave>",       self._cancel,   add="+")
        widget.bind("<ButtonPress>", self._cancel,   add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job = self._widget.after(self._DELAY, self._show)

    def _cancel(self, _=None):
        if self._job:
            self._widget.after_cancel(self._job)
            self._job = None
        self._hide()

    def _show(self):
        if self._tip_win:
            return
        w = self._widget
        x = w.winfo_rootx() + 14
        y = w.winfo_rooty() + w.winfo_height() + 5
        self._tip_win = tw = tk.Toplevel(w)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        tw.wm_geometry(f"+{x}+{y}")
        outer = tk.Frame(tw, bg=self._BORDER, padx=1, pady=1)
        outer.pack()
        tk.Label(
            outer,
            text=self._text,
            bg=self._BG, fg=self._FG,
            font=("Segoe UI", 9),
            padx=10, pady=5,
            wraplength=320,
            justify="left",
        ).pack()

    def _hide(self):
        if self._tip_win:
            self._tip_win.destroy()
            self._tip_win = None


def tip(widget: tk.Widget, text: str) -> ToolTip:
    """Atajo para añadir un tooltip a cualquier widget."""
    return ToolTip(widget, text)


def tab_desc(parent: tk.Widget, text: str):
    """
    Crea una barra de descripción al tope de una pestaña.
    Muestra brevemente el propósito de la sección.
    """
    bar = tk.Frame(parent, bg="#1c2e3f", pady=4)
    bar.pack(fill="x", side="top")
    tk.Label(
        bar,
        text=f"  ℹ  {text}",
        bg="#1c2e3f", fg="#95a5a6",
        font=("Segoe UI", 9),
        anchor="w",
    ).pack(fill="x", padx=8)


# ─── Helper: barra de botones CRUD ───────────────────────────────────────────

def crud_toolbar(parent, on_add=None, on_edit=None, on_delete=None, extras=None,
                 tip_add="", tip_edit="", tip_del="", tips_extras=None):
    """
    Crea una barra horizontal con botones Añadir / Editar / Eliminar + extras.
    `extras`      = [(texto, callback), ...]
    `tips_extras` = [tooltip_texto, ...] (mismo orden que extras)
    Retorna el frame.
    """
    frm = ttk.Frame(parent)
    if on_add:
        b = ttk.Button(frm, text="➕  Añadir", style="Acc.TButton", command=on_add)
        b.pack(side="left", padx=(0, 4), pady=4)
        if tip_add:
            ToolTip(b, tip_add)
    if on_edit:
        b = ttk.Button(frm, text="✏  Editar", style="Acc.TButton", command=on_edit)
        b.pack(side="left", padx=4, pady=4)
        if tip_edit:
            ToolTip(b, tip_edit)
    if on_delete:
        b = ttk.Button(frm, text="🗑  Eliminar", command=on_delete)
        b.pack(side="left", padx=4, pady=4)
        if tip_del:
            ToolTip(b, tip_del)
    if extras:
        tips_extras = tips_extras or []
        for i, (txt, cmd) in enumerate(extras):
            b = ttk.Button(frm, text=txt, command=cmd)
            b.pack(side="left", padx=4, pady=4)
            if i < len(tips_extras) and tips_extras[i]:
                ToolTip(b, tips_extras[i])
    return frm


# ─── Diálogo genérico (ventana modal) ────────────────────────────────────────

class SimpleDialog(tk.Toplevel):
    """
    Ventana modal reutilizable para formularios CRUD.
    Subclasificar y sobreescribir `_build_form` y `_get_values`.
    """

    def __init__(self, parent, title="Editar"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self.result = None

        self._build_form()
        self._build_buttons()

        self.transient(parent)
        self.grab_set()
        self.update_idletasks()
        # Centrar respecto al parent
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build_form(self):
        pass

    def _get_values(self):
        return None

    def _build_buttons(self):
        frm = tk.Frame(self, bg=C["bg"])
        frm.pack(fill="x", padx=14, pady=(4, 10))
        ttk.Button(frm, text="✔  Guardar", style="Acc.TButton",
                   command=self._ok).pack(side="right", padx=4)
        ttk.Button(frm, text="Cancelar",
                   command=self.destroy).pack(side="right")

    def _ok(self):
        try:
            self.result = self._get_values()
        except ValueError as e:
            from tkinter import messagebox
            messagebox.showerror("Error", str(e), parent=self)
            return
        self.destroy()

    def wait(self):
        self.wait_window()
        return self.result
