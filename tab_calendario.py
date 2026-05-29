"""
tab_calendario.py — Pestaña Calendario: Calendario de Compras + Ciclos de Demanda
==================================================================================
Sub-pestañas:
  • Calendario — Timeline mensual de pedidos (pendientes y próximos)
  • Ciclos de Demanda — Gráfica matplotlib del nivel de inventario por SKU
  • Modelos Lotificación — POQ y Lote×Lote por SKU/consumible
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import database as db
from eoq_models import InventarioEOQ, POQModel, LoteXLote, DescuentosCantidad
from gui_utils import C, F_LABEL, F_BOLD, F_MONO, F_SMALL, _entry_row, _flt, make_treeview, tip


# ═══════════════════════════════════════════════════════════════════════════════
# Calendario de Compras
# ═══════════════════════════════════════════════════════════════════════════════

class _TabCalendario(ttk.Frame):
    """
    Lista todos los pedidos agrupados por mes.
    Permite generar pedidos automáticos desde parámetros EOQ de un SKU.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ttk.Label(ctrl, text="Mes/Año :", style="In.TLabel").pack(side="left", padx=(4, 2))
        self.vMes = tk.StringVar(value=datetime.now().strftime("%Y-%m"))
        ttk.Entry(ctrl, textvariable=self.vMes, width=8).pack(side="left", padx=2)
        b_fil = ttk.Button(ctrl, text="🔄 Filtrar mes", command=self.refresh)
        b_fil.pack(side="left", padx=4)
        tip(b_fil, "Mostrar solo los pedidos del mes/año indicado (formato YYYY-MM).")
        b_all = ttk.Button(ctrl, text="Todos", command=self._mostrar_todos)
        b_all.pack(side="left", padx=2)
        tip(b_all, "Mostrar todos los pedidos sin filtro de mes.")
        b_exp = ttk.Button(ctrl, text="💾 Exportar CSV", command=self._exportar)
        b_exp.pack(side="right", padx=6)
        tip(b_exp, "Exportar el calendario de pedidos actual a un archivo CSV.")

        COLS = ("ID", "Fecha Orden", "SKU", "Descripción", "Proveedor",
                "Cantidad", "Unidad", "Total ($)", "Estado", "Entrega Esperada")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))

        self._tv.column("ID",           width=40)
        self._tv.column("Fecha Orden",  width=95)
        self._tv.column("SKU",          width=80)
        self._tv.column("Descripción",  width=160)
        self._tv.column("Proveedor",    width=130)
        self._tv.column("Cantidad",     width=75)
        self._tv.column("Unidad",       width=65)
        self._tv.column("Total ($)",    width=85)
        self._tv.column("Estado",       width=85)
        self._tv.column("Entrega Esperada", width=110)

        self._tv.tag_configure("recibido",  background="#1a3a2a", foreground=C["texto"])
        self._tv.tag_configure("cancelado", background="#3a1a1a", foreground=C["dim"])
        self._tv.tag_configure("pendiente", background=C["panel"], foreground=C["texto"])

        # Resumen
        self._lbl_resumen = ttk.Label(self, text="", style="Dim.TLabel")
        self._lbl_resumen.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 4))

        self.refresh()

    def _cargar(self, pedidos):
        self._tv.delete(*self._tv.get_children())
        total_val = 0
        for r in pedidos:
            total = round(r["cantidad"] * r["precio_unitario"], 2)
            total_val += total
            tag = r["estado"]
            self._tv.insert("", "end", tags=(tag,), values=(
                r["id"], r["fecha_orden"],
                r["sku_codigo"] or "", r["sku_desc"] or "",
                r["proveedor_nombre"] or "",
                r["cantidad"], r["unidad"],
                total, r["estado"], r["fecha_entrega_esperada"]
            ))
        n = len(pedidos)
        self._lbl_resumen.config(
            text=f"  {n} pedido(s)  |  Total: ${total_val:,.2f}")

    def refresh(self):
        mes = self.vMes.get().strip()
        todos = db.get_pedidos()
        if mes:
            filtrado = [p for p in todos if str(p["fecha_orden"]).startswith(mes)]
        else:
            filtrado = todos
        self._cargar(filtrado)

    def _mostrar_todos(self):
        self.vMes.set("")
        self._cargar(db.get_pedidos())

    def _exportar(self):
        pedidos = db.get_pedidos()
        if not pedidos:
            messagebox.showinfo("Sin datos", "No hay pedidos."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            title="Exportar calendario de compras"
        )
        if path:
            pd.DataFrame(pedidos).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Calendario exportado en:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Ciclos de Demanda (gráfica de inventario por SKU)
# ═══════════════════════════════════════════════════════════════════════════════

class _TabCiclosDemanda(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._fig = None
        self._build()

    def _build(self):
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(ctrl, text="SKU :", style="In.TLabel").pack(side="left", padx=(4, 2))
        self._skus = db.get_skus()
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar(value=self._sku_labels[0] if self._sku_labels else "")
        self._cb  = ttk.Combobox(ctrl, textvariable=self.vSKU,
                                  values=self._sku_labels, state="readonly", width=26)
        self._cb.pack(side="left", padx=2)

        # Parámetros EOQ rápidos para la gráfica
        ttk.Label(ctrl, text="D anual :", style="In.TLabel").pack(side="left", padx=(8, 2))
        self.vD  = tk.StringVar(value="1000")
        ttk.Entry(ctrl, textvariable=self.vD, width=7).pack(side="left", padx=2)

        ttk.Label(ctrl, text="S :", style="In.TLabel").pack(side="left", padx=(6, 2))
        self.vS  = tk.StringVar(value="50")
        ttk.Entry(ctrl, textvariable=self.vS, width=6).pack(side="left", padx=2)

        ttk.Label(ctrl, text="H :", style="In.TLabel").pack(side="left", padx=(6, 2))
        self.vH  = tk.StringVar(value="2")
        ttk.Entry(ctrl, textvariable=self.vH, width=6).pack(side="left", padx=2)

        ttk.Label(ctrl, text="SS :", style="In.TLabel").pack(side="left", padx=(6, 2))
        self.vSS = tk.StringVar(value="0")
        ttk.Entry(ctrl, textvariable=self.vSS, width=6).pack(side="left", padx=2)

        ttk.Label(ctrl, text="Días :", style="In.TLabel").pack(side="left", padx=(6, 2))
        self.vDias = tk.StringVar(value="365")
        ttk.Entry(ctrl, textvariable=self.vDias, width=6).pack(side="left", padx=2)

        b_graf = ttk.Button(ctrl, text="📈 Graficar", style="Acc.TButton",
                   command=self._graficar)
        b_graf.pack(side="left", padx=8)
        tip(b_graf, "Generar gráfica de ciclos de inventario (nivel de stock vs tiempo) para el SKU seleccionado.")
        b_multi = ttk.Button(ctrl, text="📊 Multi-SKU",
                   command=self._graficar_multi)
        b_multi.pack(side="left", padx=2)
        tip(b_multi, "Comparar curvas de inventario de múltiples SKUs en una sola gráfica.")

        # Info auto-llenado
        info = ttk.Label(self,
                          text="  Tip: seleccione un SKU — los parámetros D, S, H, SS se sugieren "
                               "automáticamente si hay consumibles configurados.",
                          style="Dim.TLabel")
        info.grid(row=1, column=0, sticky="w", padx=6, pady=0)

        self._frame_graf = ttk.Frame(self)
        self._frame_graf.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
        self._frame_graf.rowconfigure(0, weight=1)
        self._frame_graf.columnconfigure(0, weight=1)

        self._cb.bind("<<ComboboxSelected>>", self._on_sku_selected)

    def _on_sku_selected(self, _=None):
        """Auto-llena SS desde consumibles y D desde clientes."""
        idx = self._sku_labels.index(self.vSKU.get()) if self.vSKU.get() in self._sku_labels else -1
        if idx < 0: return
        sku_id = self._sku_ids[idx]
        cons   = db.get_consumible_by_sku(sku_id)
        if cons:
            self.vSS.set(str(cons["stock_seguridad"]))
        demanda = db.get_demanda_total_sku(sku_id)
        if demanda > 0:
            self.vD.set(str(demanda))

    def _cerrar_fig(self):
        if self._fig:
            plt.close(self._fig)
            self._fig = None

    def _graficar(self):
        try:
            D    = _flt(self.vD,    "D",    0.01)
            S    = _flt(self.vS,    "S",    0.01)
            H    = _flt(self.vH,    "H",    0.01)
            SS   = _flt(self.vSS,   "SS",   0)
            dias = int(_flt(self.vDias, "Días", 1))
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return

        self._cerrar_fig()
        for w in self._frame_graf.winfo_children():
            w.destroy()

        sku_label = self.vSKU.get()
        m = InventarioEOQ(D, S, H, SS=SS)
        t, inv = m.serie_inventario(dias)
        r = m.calcular_costos()

        fig, ax = plt.subplots(figsize=(9, 4.2))
        fig.patch.set_facecolor(C["graf_bg"])
        ax.set_facecolor(C["graf_bg"])
        ax.plot(t, inv, color=C["inv"], linewidth=1.9, label=f"{sku_label}")
        ax.fill_between(t, inv, alpha=0.12, color=C["inv"])
        if SS > 0:
            ax.axhline(y=SS, color=C["ss"], linestyle="--",
                       linewidth=1.3, label=f"SS = {SS:.0f} u")
        ax.axhline(y=r["punto_reorden"], color=C["rop"], linestyle=":",
                   linewidth=1.3, label=f"ROP = {r['punto_reorden']:.1f} u")

        ax.set_title(f"Ciclo de Inventario — {sku_label}  |  Q*={r['Q_optimo']:.1f} u",
                     color=C["texto"], fontsize=11, pad=10)
        ax.set_xlabel("Tiempo (días)", color=C["dim"], fontsize=10)
        ax.set_ylabel("Unidades en inventario", color=C["dim"], fontsize=10)
        ax.tick_params(colors=C["dim"])
        for sp in ax.spines.values():
            sp.set_color(C["grid"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, color=C["grid"], alpha=0.5, linestyle="--")
        ax.legend(fontsize=9, facecolor=C["panel"],
                  labelcolor=C["texto"], edgecolor=C["grid"])
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._frame_graf)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        frm_tb = ttk.Frame(self._frame_graf)
        frm_tb.grid(row=1, column=0, sticky="ew")
        NavigationToolbar2Tk(canvas, frm_tb)
        self._fig = fig

    def _graficar_multi(self):
        """Grafíca todos los SKUs con consumibles configurados en una sola figura."""
        consumibles = db.get_consumibles()
        if not consumibles:
            messagebox.showinfo("Sin datos", "No hay consumibles configurados."); return

        try:
            S    = _flt(self.vS,    "S",    0.01)
            H    = _flt(self.vH,    "H",    0.01)
            dias = int(_flt(self.vDias, "Días", 1))
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return

        self._cerrar_fig()
        for w in self._frame_graf.winfo_children():
            w.destroy()

        n    = len(consumibles)
        cols = min(n, 3)
        rows = math.ceil(n / cols)
        fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 3.5 * rows))
        fig.patch.set_facecolor(C["graf_bg"])
        if n == 1:
            axes = [axes]
        elif rows == 1:
            axes = list(axes)
        else:
            axes = [ax for row in axes for ax in row]

        COLORS = [C["inv"], C["verde"], C["rop"], "#9b59b6", "#1abc9c", "#e67e22"]

        for i, cons in enumerate(consumibles):
            ax    = axes[i]
            ax.set_facecolor(C["graf_bg"])
            sku_id = cons["sku_id"]
            D      = db.get_demanda_total_sku(sku_id) or 100
            SS     = cons["stock_seguridad"]
            try:
                m      = InventarioEOQ(D, S, H, SS=SS)
                t, inv = m.serie_inventario(dias)
                color  = COLORS[i % len(COLORS)]
                ax.plot(t, inv, color=color, linewidth=1.6)
                ax.fill_between(t, inv, alpha=0.1, color=color)
                if SS > 0:
                    ax.axhline(y=SS, color=C["ss"], linestyle="--",
                               linewidth=1, alpha=0.8)
                r = m.calcular_costos()
                ax.axhline(y=r["punto_reorden"], color=C["rop"],
                           linestyle=":", linewidth=1, alpha=0.8)
            except Exception:
                pass
            ax.set_title(f"{cons['codigo']}", color=C["texto"], fontsize=9, pad=6)
            ax.set_xlabel("días", color=C["dim"], fontsize=7)
            ax.set_ylabel("u", color=C["dim"], fontsize=7)
            ax.tick_params(colors=C["dim"], labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(C["grid"])
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.grid(True, color=C["grid"], alpha=0.4, linestyle="--")

        # Ocultar ejes sobrantes
        for j in range(n, len(axes)):
            axes[j].set_visible(False)

        fig.suptitle("Ciclos de Demanda — Todos los Consumibles",
                     color=C["texto"], fontsize=12, y=1.01)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._frame_graf)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        frm_tb = ttk.Frame(self._frame_graf)
        frm_tb.grid(row=1, column=0, sticky="ew")
        NavigationToolbar2Tk(canvas, frm_tb)
        self._fig = fig

    def refresh(self):
        self._skus = db.get_skus()
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self._cb["values"] = self._sku_labels


# ═══════════════════════════════════════════════════════════════════════════════
# Modelos de Lotificación (POQ + Lote×Lote)
# ═══════════════════════════════════════════════════════════════════════════════

class _TabLotificacion(ttk.Frame):
    """Aplica modelos POQ o LxL a un consumible y muestra el plan período a período."""

    MODELOS = ["POQ (Period Order Quantity)", "Lote × Lote (L×L)"]

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        piz = ttk.Frame(self, style="Panel.TFrame", width=300)
        piz.grid(row=0, column=0, sticky="nsew", rowspan=4, padx=(6, 2), pady=6)
        piz.grid_propagate(False)
        piz.columnconfigure(1, weight=1)

        ttk.Label(piz, text="Parámetros Lotificación",
                  style="Tit.TLabel").grid(row=0, column=0, columnspan=2,
                                            sticky="w", padx=10, pady=(10, 4))

        ttk.Label(piz, text="Modelo :", style="In.TLabel").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vModelo = tk.StringVar(value=self.MODELOS[0])
        ttk.Combobox(piz, textvariable=self.vModelo, values=self.MODELOS,
                     state="readonly", width=20).grid(
            row=1, column=1, sticky="ew", padx=(0, 10), pady=3)

        self.vS        = _entry_row(piz, "Costo pedido (S) :",  50,  2, ancho=10)
        self.vH        = _entry_row(piz, "Costo mant./u/per :", 2,   3, ancho=10)
        self.vPeriodos = _entry_row(piz, "Períodos/año :",       12,  4, ancho=10)

        ttk.Separator(piz, orient="horizontal").grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=6)
        ttk.Label(piz, text="Demandas por período",
                  style="Sub.TLabel").grid(row=6, column=0, columnspan=2,
                                            sticky="w", padx=10)
        ttk.Label(piz,
                  text="(una por línea, ej. 120↵80↵95...)",
                  style="Dim.TLabel").grid(row=7, column=0, columnspan=2,
                                            sticky="w", padx=10)

        self._txt_demandas = tk.Text(piz, height=10, width=16,
                                      bg=C["input_bg"], fg=C["texto"],
                                      insertbackground=C["texto"],
                                      font=("Consolas", 9), relief="flat")
        self._txt_demandas.grid(row=8, column=0, columnspan=2,
                                 sticky="nsew", padx=10, pady=4)
        self._txt_demandas.insert("end", "\n".join(["100"] * 12))

        b_calc = ttk.Button(piz, text="⚙ Calcular", style="Acc.TButton",
                   command=self._calcular)
        b_calc.grid(row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
        tip(b_calc, "Calcular plan de lotificación período a período con el modelo seleccionado (EOQ, LxL, POQ).")

        # Panel derecho: tabla + resumen
        pder = ttk.Frame(self)
        pder.grid(row=0, column=1, sticky="nsew", padx=(2, 6), pady=6, rowspan=4)
        pder.rowconfigure(1, weight=1)
        pder.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self._lbl_resumen = ttk.Label(pder, text="Configure parámetros y presione Calcular.",
                                       style="In.TLabel")
        self._lbl_resumen.grid(row=0, column=0, sticky="w", padx=6, pady=(6, 2))

        COLS = ("Período", "Demanda", "Inv. Inicial", "Pedido",
                "Inv. Final", "Costo Pedido", "Costo Mant.")
        frm_tv, self._tv = make_treeview(pder, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
        for c in COLS:
            self._tv.column(c, width=90)

        b_exp2 = ttk.Button(pder, text="💾 Exportar CSV",
                   command=self._exportar)
        b_exp2.grid(row=2, column=0, sticky="e", padx=6, pady=4)
        tip(b_exp2, "Exportar la tabla de lotificación calculada a CSV.")
        self._last_df = None

    def _calcular(self):
        try:
            S        = _flt(self.vS,        "S",         0.01)
            H        = _flt(self.vH,        "H",         0.01)
            periodos = int(_flt(self.vPeriodos, "Períodos", 1))
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return

        raw = self._txt_demandas.get("1.0", "end").strip().split()
        try:
            demandas = [float(x.replace(",", ".")) for x in raw if x]
        except ValueError:
            messagebox.showerror("Error", "Las demandas deben ser números (uno por línea)."); return

        if not demandas:
            messagebox.showerror("Error", "Ingrese al menos una demanda."); return

        modelo_nombre = self.vModelo.get()
        try:
            if "POQ" in modelo_nombre:
                D_total = sum(demandas)
                m = POQModel(D_total, S, H, periodos=len(demandas), demandas=demandas)
                df = m.calcular_plan()
                res = m.calcular_costos_totales()
                txt = (f"  T = {res['T_periodos']} período(s)  |  "
                       f"Pedidos: {res['num_pedidos']}  |  "
                       f"Costo pedidos: ${res['costo_pedidos']:.2f}  |  "
                       f"Costo mant.: ${res['costo_mant']:.2f}  |  "
                       f"Costo total: ${res['costo_total']:.2f}")
            else:
                m = LoteXLote(S, H, demandas)
                df = m.calcular_plan()
                res = m.calcular_costos_totales()
                txt = (f"  Pedidos: {res['num_pedidos']}  |  "
                       f"Costo pedidos: ${res['costo_pedidos']:.2f}  |  "
                       f"Costo mant.: ${res['costo_mant']:.2f}  |  "
                       f"Costo total: ${res['costo_total']:.2f}")
        except Exception as e:
            messagebox.showerror("Error de cálculo", str(e)); return

        self._lbl_resumen.config(text=txt)
        self._tv.delete(*self._tv.get_children())
        for _, row in df.iterrows():
            tag = "pedido" if row["Pedido"] > 0 else ""
            self._tv.insert("", "end", tags=(tag,), values=list(row))
        self._tv.tag_configure("pedido", foreground=C["verde"])
        self._last_df = df

    def _exportar(self):
        if self._last_df is None:
            messagebox.showinfo("Sin datos", "Primero calcule el plan."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            title="Exportar plan de lotificación"
        )
        if path:
            self._last_df.to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Plan exportado en:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tab Calendario principal
# ═══════════════════════════════════════════════════════════════════════════════

class TabCalendario(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self._tab_cal    = _TabCalendario(nb)
        self._tab_ciclos = _TabCiclosDemanda(nb)
        self._tab_lotif  = _TabLotificacion(nb)

        nb.add(self._tab_cal,    text="  📅 Calendario Compras  ")
        nb.add(self._tab_ciclos, text="  📈 Ciclos de Demanda  ")
        nb.add(self._tab_lotif,  text="  🔢 Lotificación POQ/LxL  ")

    def refresh_all(self):
        self._tab_cal.refresh()
        self._tab_ciclos.refresh()
