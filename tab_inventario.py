"""
tab_inventario.py — Pestaña Inventario: Stock | Alertas | Importar CSV
=======================================================================
Sub-pestañas:
  • Stock   — Niveles actuales de todos los SKUs, edición de stock
  • Alertas — SKUs por debajo de la política de seguridad
  • Importar CSV — Carga masiva de datos desde CSV
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import database as db
from gui_utils import C, F_LABEL, F_BOLD, F_SMALL, _entry_row, _flt, make_treeview, SimpleDialog, tip


# ═══════════════════════════════════════════════════════════════════════════════
# Stock Actual
# ═══════════════════════════════════════════════════════════════════════════════

class _StockEditDialog(SimpleDialog):
    def __init__(self, parent, sku):
        self._sku = sku
        super().__init__(parent, f"Actualizar Stock — {sku['codigo']}")

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text=f"SKU: {self._sku['codigo']} — {self._sku['descripcion']}",
                  style="Sub.TLabel").grid(row=0, column=0, columnspan=2,
                                            sticky="w", padx=10, pady=(0, 6))
        self.vStock = _entry_row(f, "Nuevo stock actual :", self._sku["stock_actual"], 1)

    def _get_values(self):
        return {"cantidad": _flt(self.vStock, "Stock", 0)}


class _TabStock(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        b_ref = ttk.Button(ctrl, text="🔄 Actualizar", command=self.refresh)
        b_ref.pack(side="left", padx=4)
        tip(b_ref, "Recargar el inventario desde la base de datos.")
        b_edit = ttk.Button(ctrl, text="✏ Editar Stock", style="Acc.TButton",
                   command=self._edit_stock)
        b_edit.pack(side="left", padx=4)
        tip(b_edit, "Ajustar manualmente el stock actual del SKU seleccionado.")
        b_exp = ttk.Button(ctrl, text="💾 Exportar CSV",
                   command=self._exportar)
        b_exp.pack(side="right", padx=4)
        tip(b_exp, "Exportar la vista actual del inventario a un archivo CSV.")

        COLS = ("ID", "Código", "Descripción", "Tipo", "Unidad",
                "Stock Actual", "Stock Seguridad", "Estado")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("ID",            width=40)
        self._tv.column("Código",        width=90)
        self._tv.column("Descripción",   width=180)
        self._tv.column("Tipo",          width=90)
        self._tv.column("Unidad",        width=70)
        self._tv.column("Stock Actual",  width=90)
        self._tv.column("Stock Seguridad", width=105)
        self._tv.column("Estado",        width=80)

        self._tv.tag_configure("alerta", background="#3a1a1a", foreground=C["ss"])
        self._tv.tag_configure("ok",     background=C["panel"], foreground=C["texto"])

        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        # Mapa de stock seguridad por sku_id
        cons_map = {c["sku_id"]: c["stock_seguridad"] for c in db.get_consumibles()}
        for s in db.get_skus():
            ss     = cons_map.get(s["id"], 0)
            estado = "⚠ ALERTA" if s["stock_actual"] <= ss and ss > 0 else "✔ OK"
            tag    = "alerta" if estado.startswith("⚠") else "ok"
            self._tv.insert("", "end", tags=(tag,), values=(
                s["id"], s["codigo"], s["descripcion"], s["tipo"],
                s["unidad"], s["stock_actual"], ss, estado
            ))

    def _selected_sku(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un SKU."); return None
        v = self._tv.item(sel[0])["values"]
        return db.get_sku(v[0])

    def _edit_stock(self):
        sku = self._selected_sku()
        if not sku: return
        dlg = _StockEditDialog(self.winfo_toplevel(), sku)
        res = dlg.wait()
        if res:
            db.update_stock(sku["id"], res["cantidad"])
            self.refresh()

    def _exportar(self):
        skus = db.get_skus()
        if not skus:
            messagebox.showinfo("Sin datos", "No hay SKUs registrados."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            title="Exportar stock"
        )
        if path:
            pd.DataFrame(skus).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Stock exportado en:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Alertas de Inventario
# ═══════════════════════════════════════════════════════════════════════════════

class _TabAlertas(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ttk.Label(ctrl,
                  text="⚠  SKUs cuyo stock actual ≤ stock de seguridad",
                  style="In.TLabel").pack(side="left", padx=6)
        ttk.Button(ctrl, text="🔄 Actualizar", command=self.refresh).pack(side="right", padx=6)

        COLS = ("Código", "Descripción", "Unidad", "Stock Actual",
                "Stock Seguridad", "Déficit", "Política SS")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("Código",        width=90)
        self._tv.column("Descripción",   width=190)
        self._tv.column("Unidad",        width=70)
        self._tv.column("Stock Actual",  width=95)
        self._tv.column("Stock Seguridad", width=110)
        self._tv.column("Déficit",       width=80)
        self._tv.column("Política SS",   width=100)

        self._tv.tag_configure("critico",  background="#5a0a0a", foreground="#ff6b6b")
        self._tv.tag_configure("alerta",   background="#3a1a1a", foreground=C["ss"])

        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_alertas_stock():
            deficit = round(r["stock_seguridad"] - r["stock_actual"], 2)
            tag     = "critico" if deficit > r["stock_seguridad"] * 0.5 else "alerta"
            self._tv.insert("", "end", tags=(tag,), values=(
                r["codigo"], r["descripcion"], r["unidad"],
                r["stock_actual"], r["stock_seguridad"],
                deficit, r["politica_seguridad"]
            ))


# ═══════════════════════════════════════════════════════════════════════════════
# Importar CSV
# ═══════════════════════════════════════════════════════════════════════════════

class _TabImportarCSV(ttk.Frame):
    """Permite importar SKUs y stock desde un archivo CSV."""

    _PLANTILLA_COLS = ["codigo", "descripcion", "unidad", "stock_actual", "precio_venta", "tipo"]

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        self._df = None
        self._build()

    def _build(self):
        # Instrucciones
        info = ttk.Frame(self, style="Panel.TFrame")
        info.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ttk.Label(info,
                  text=(
                      "  Formato esperado del CSV — columnas: "
                      "codigo | descripcion | unidad | stock_actual | precio_venta | tipo\n"
                      "  El campo 'tipo' puede ser: producto | consumible | materia_prima  "
                      "  •  Columnas adicionales son ignoradas."
                  ),
                  style="Dim.TLabel").pack(padx=6, pady=6, anchor="w")

        # Controles
        ctrl = ttk.Frame(self)
        ctrl.grid(row=1, column=0, sticky="ew", padx=6, pady=2)
        b_abrir = ttk.Button(ctrl, text="📂 Abrir CSV", style="Acc.TButton",
                   command=self._abrir)
        b_abrir.pack(side="left", padx=4)
        tip(b_abrir, "Seleccionar un archivo CSV con columnas: codigo, descripcion, unidad, stock_actual, precio_venta, tipo.")
        b_plt = ttk.Button(ctrl, text="💾 Plantilla CSV",
                   command=self._descargar_plantilla)
        b_plt.pack(side="left", padx=4)
        tip(b_plt, "Descargar una plantilla CSV vacía con el formato correcto para rellenar e importar.")
        self._lbl_archivo = ttk.Label(ctrl, text="Ningún archivo seleccionado",
                                       style="Dim.TLabel")
        self._lbl_archivo.pack(side="left", padx=10)

        # Botón importar
        ctrl2 = ttk.Frame(self)
        ctrl2.grid(row=2, column=0, sticky="ew", padx=6, pady=2)
        b_imp = ttk.Button(ctrl2, text="⬆  Importar datos", style="Acc.TButton",
                   command=self._importar)
        b_imp.pack(side="left", padx=4)
        tip(b_imp, "Importar los SKUs del CSV seleccionado al inventario. Los códigos existentes actualizan su stock.")
        self._lbl_estado = ttk.Label(ctrl2, text="", style="In.TLabel")
        self._lbl_estado.pack(side="left", padx=10)

        # Preview
        COLS = ("codigo", "descripcion", "unidad", "stock_actual", "precio_venta", "tipo")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=3, column=0, sticky="nsew", padx=6, pady=(0, 6))
        for c in COLS:
            self._tv.column(c, width=110)

    def _abrir(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            title="Abrir CSV de inventario"
        )
        if not path:
            return
        try:
            self._df = pd.read_csv(path)
        except Exception as e:
            messagebox.showerror("Error al leer CSV", str(e)); return

        self._lbl_archivo.config(text=path.split("\\")[-1])
        self._lbl_estado.config(text="")
        self._preview()

    def _preview(self):
        self._tv.delete(*self._tv.get_children())
        if self._df is None: return
        for _, row in self._df.head(50).iterrows():
            vals = [row.get(c, "") for c in self._PLANTILLA_COLS]
            self._tv.insert("", "end", values=vals)

    def _importar(self):
        if self._df is None:
            messagebox.showwarning("Sin datos", "Primero abra un CSV."); return

        ok = 0; errores = []
        for i, row in self._df.iterrows():
            try:
                codigo     = str(row.get("codigo", "")).strip().upper()
                desc       = str(row.get("descripcion", "")).strip()
                unidad     = str(row.get("unidad", "unidad")).strip() or "unidad"
                stock      = float(row.get("stock_actual", 0) or 0)
                precio     = float(row.get("precio_venta", 0) or 0)
                tipo       = str(row.get("tipo", "producto")).strip()
                if not codigo or not desc:
                    raise ValueError("Código o descripción vacíos")
                # Upsert: si ya existe actualiza, si no, inserta
                existing = next((s for s in db.get_skus() if s["codigo"] == codigo), None)
                if existing:
                    db.update_sku(existing["id"], codigo, desc, unidad, stock, precio, tipo)
                else:
                    db.add_sku(codigo, desc, unidad, stock, precio, tipo)
                ok += 1
            except Exception as e:
                errores.append(f"Fila {i+2}: {e}")

        msg = f"Importados: {ok} SKUs."
        if errores:
            msg += f"\nErrores ({len(errores)}):\n" + "\n".join(errores[:10])
        messagebox.showinfo("Importación completada", msg)
        self._lbl_estado.config(text=f"✔ {ok} registros importados")

    def _descargar_plantilla(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="plantilla_skus.csv",
            title="Guardar plantilla"
        )
        if path:
            plantilla = pd.DataFrame(columns=self._PLANTILLA_COLS)
            # Ejemplo
            plantilla.loc[0] = ["SKU001", "Producto de ejemplo", "unidad", 100, 25.0, "producto"]
            plantilla.to_csv(path, index=False)
            messagebox.showinfo("Plantilla guardada", f"Plantilla CSV guardada en:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Proyección de Inventario (stock + pedidos pendientes + demanda clientes)
# ═══════════════════════════════════════════════════════════════════════════════

class _TabProyeccionInventario(ttk.Frame):
    """
    Proyecta el nivel de inventario de un SKU combinando:
      • Stock actual del SKU
      • Pedidos pendientes (entradas): fecha_orden + lead_time del proveedor
      • Demanda de clientes vía cliente_consumo (directa) + BOM derivado (salidas)
    Todas las cantidades se redondean con math.ceil.
    Muestra tabla y gráfica matplotlib de la proyección período a período.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._fig    = None
        self._canvas = None
        self._proyeccion = []
        self._build()

    def _build(self):
        # ── Controles superiores ──────────────────────────────────────────
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(ctrl, text="SKU :", style="In.TLabel").pack(side="left", padx=(4, 2))
        self._skus = db.get_skus()
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar(value=self._sku_labels[0] if self._sku_labels else "")
        self._cb_sku = ttk.Combobox(ctrl, textvariable=self.vSKU,
                                     values=self._sku_labels, state="readonly", width=26)
        self._cb_sku.pack(side="left", padx=2)

        ttk.Label(ctrl, text="Períodos :", style="In.TLabel").pack(side="left", padx=(8, 2))
        self.vPeriodos = tk.StringVar(value="12")
        ttk.Entry(ctrl, textvariable=self.vPeriodos, width=5, style="In.TEntry").pack(
            side="left", padx=2)

        ttk.Label(ctrl, text="Tipo :", style="In.TLabel").pack(side="left", padx=(8, 2))
        self.vTipo = tk.StringVar(value="mes")
        ttk.Combobox(ctrl, textvariable=self.vTipo, values=["mes", "semana"],
                     state="readonly", width=8).pack(side="left", padx=2)

        b_proy = ttk.Button(ctrl, text="📈 Proyectar", style="Acc.TButton",
                             command=self._proyectar)
        b_proy.pack(side="left", padx=8)
        tip(b_proy, "Calcula la proyección de inventario período a período\n"
                    "usando pedidos pendientes y demanda de clientes (ceil).")

        b_exp = ttk.Button(ctrl, text="💾 Exportar CSV", command=self._exportar)
        b_exp.pack(side="right", padx=6)
        tip(b_exp, "Exportar la proyección a un archivo CSV.")

        # ── Nota ──────────────────────────────────────────────────────────
        nota = ttk.Label(
            self,
            text="  Entradas: pedidos pendientes con lead time del proveedor. "
                 "Salidas: demanda directa (cliente_consumo) + derivada (BOM). "
                 "Cantidades redondeadas con ceil.",
            style="Dim.TLabel",
        )
        nota.grid(row=1, column=0, sticky="w", padx=6, pady=(0, 2))

        # ── Panel dividido: tabla izquierda | gráfica derecha ─────────────
        panel = ttk.Frame(self)
        panel.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 4))
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=0)
        panel.columnconfigure(1, weight=1)

        # Tabla
        COLS = ("Período", "Stock Inicial", "Entradas (↑)", "Salidas (↑)", "Stock Final")
        frm_tv, self._tv = make_treeview(panel, COLS, height=14)
        frm_tv.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self._tv.column("Período",        width=75)
        self._tv.column("Stock Inicial",  width=100)
        self._tv.column("Entradas (↑)",   width=90)
        self._tv.column("Salidas (↑)",    width=90)
        self._tv.column("Stock Final",    width=95)
        self._tv.tag_configure("deficit",  background="#3a1a1a", foreground="#e74c3c")
        self._tv.tag_configure("normal",   background="#1e3028", foreground="#ecf0f1")

        # Gráfica
        self._graf_frame = ttk.Frame(panel, style="Panel.TFrame")
        self._graf_frame.grid(row=0, column=1, sticky="nsew")
        self._graf_frame.rowconfigure(0, weight=1)
        self._graf_frame.columnconfigure(0, weight=1)

    def _proyectar(self):
        if not self._sku_ids:
            messagebox.showinfo("Sin SKUs", "No hay SKUs registrados."); return
        try:
            n = int(self.vPeriodos.get())
            if n < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Número de períodos inválido."); return

        idx = self._sku_labels.index(self.vSKU.get()) if self.vSKU.get() in self._sku_labels else 0
        sku_id = self._sku_ids[idx]

        self._skus = db.get_skus()
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self._cb_sku["values"] = self._sku_labels

        self._proyeccion = db.proyectar_inventario(sku_id, n, self.vTipo.get())
        self._cargar_tabla(self._proyeccion)
        self._graficar(self._proyeccion)

    def _cargar_tabla(self, filas):
        self._tv.delete(*self._tv.get_children())
        for r in filas:
            tag = "deficit" if r["stock_final"] < 0 else "normal"
            self._tv.insert("", "end", tags=(tag,), values=(
                r["label"],
                r["stock_inicial"],
                r["entradas"],
                r["salidas"],
                r["stock_final"],
            ))

    def _graficar(self, filas):
        # Limpiar gráfica anterior
        for w in self._graf_frame.winfo_children():
            w.destroy()
        if self._fig:
            plt.close(self._fig)

        if not filas:
            return

        labels       = [r["label"]       for r in filas]
        stock_final  = [r["stock_final"]  for r in filas]
        entradas     = [r["entradas"]     for r in filas]
        salidas      = [r["salidas"]      for r in filas]

        bg   = C["graf_bg"]
        self._fig, ax = plt.subplots(figsize=(6, 4))
        self._fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)

        xs = range(len(labels))
        ax.bar(xs, entradas, color="#27ae60", alpha=0.6, label="Entradas")
        ax.bar(xs, [-s for s in salidas], color="#e74c3c", alpha=0.6, label="Salidas")
        ax.plot(xs, stock_final, color=C["inv"], marker="o", linewidth=2,
                label="Stock Proyectado")
        ax.axhline(0, color=C["ss"], linestyle="--", linewidth=1, alpha=0.7)

        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, rotation=45, ha="right",
                           color=C["texto"], fontsize=7)
        ax.tick_params(colors=C["texto"])
        ax.yaxis.label.set_color(C["texto"])
        ax.spines["bottom"].set_color(C["grid"])
        ax.spines["left"].set_color(C["grid"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_title("Proyección de Inventario", color=C["verde"], fontsize=10)
        ax.legend(facecolor=C["panel"], edgecolor=C["grid"],
                  labelcolor=C["texto"], fontsize=8)
        self._fig.tight_layout()

        canvas = FigureCanvasTkAgg(self._fig, master=self._graf_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._canvas = canvas

    def refresh(self):
        self._skus       = db.get_skus()
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self._cb_sku["values"] = self._sku_labels
        if self._sku_labels and self.vSKU.get() not in self._sku_labels:
            self.vSKU.set(self._sku_labels[0])

    def _exportar(self):
        if not self._proyeccion:
            messagebox.showinfo("Sin datos", "Ejecute la proyección primero."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Exportar Proyección de Inventario"
        )
        if path:
            pd.DataFrame(self._proyeccion).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Proyección exportada en:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tab Inventario principal
# ═══════════════════════════════════════════════════════════════════════════════

class TabInventario(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self._tab_stock    = _TabStock(nb)
        self._tab_alertas  = _TabAlertas(nb)
        self._tab_importar = _TabImportarCSV(nb)
        self._tab_proyec   = _TabProyeccionInventario(nb)

        nb.add(self._tab_stock,    text="  📦 Stock Actual  ")
        nb.add(self._tab_alertas,  text="  ⚠ Alertas  ")
        nb.add(self._tab_importar, text="  📂 Importar CSV  ")
        nb.add(self._tab_proyec,   text="  📈 Proyección  ")

    def refresh_all(self):
        self._tab_stock.refresh()
        self._tab_alertas.refresh()
        self._tab_proyec.refresh()
