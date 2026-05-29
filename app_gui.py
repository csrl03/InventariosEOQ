"""
app_gui.py — Interfaz gráfica del Sistema de Inventarios EOQ
============================================================
GUI con pestañas organizadas por flujo de trabajo:
  📋 Catálogos  →  📦 Inventario  →  🛒 Compras & EOQ  →  🏭 Producción  →  📅 Calendario  →  🧾 Facturas

La pestaña «Compras & EOQ» integra la lista de pedidos con los 5 modelos EOQ,
permitiendo calcular Q* y generar pedidos directamente desde los resultados.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

try:
    import ttkbootstrap as ttkb
    _HAS_TTKB = True
except ImportError:
    _HAS_TTKB = False

from eoq_models import (
    InventarioEOQ, EOQFaltantes, RevisionPeriodica,
    InventarioSeguridadContinuo, DescuentosCantidad,
)

import database as db
from gui_utils import (
    C, F_TITULO, F_LABEL, F_BOLD, F_BOTON, F_MONO, F_SMALL, F_H2,
    _entry_row, _flt, make_treeview, ToolTip, tip, tab_desc,
)
from tab_maestro     import TabMaestro
from tab_pedidos     import TabPedidos
from tab_produccion  import TabProduccion
from tab_inventario  import TabInventario
from tab_calendario  import TabCalendario
from tab_facturas    import TabFacturas

# Inicializar base de datos al arrancar
db.init_db()


# ─── Base de pestaña ──────────────────────────────────────────────────────────

class TabBase(ttk.Frame):
    """
    Frame base compartido por todos los modelos EOQ.

    Si pedidos_mode=True, agrega debajo del botón CALCULAR:
      • Selector de SKU para auto-llenado de L, SS y P desde la base de datos.
      • Indicador de stock actual / stock de seguridad.
      • Botón «✅ Crear Pedido con Q*» que abre el diálogo de nuevo pedido
        con la cantidad óptima pre-cargada.
    """

    ANCHO_PANEL = 320          # píxeles del panel izquierdo

    def __init__(self, parent, nombre_modelo, pedidos_mode: bool = False):
        super().__init__(parent)
        self._fig          = None   # matplotlib figure activa
        self._pedidos_mode = pedidos_mode
        self._last_result  = None   # último dict devuelto por calcular_costos()
        self._build_ui(nombre_modelo)

    def _build_ui(self, nombre):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Panel izquierdo ──────────────────────────────────────────────────
        piz = ttk.Frame(self, style="Panel.TFrame", width=self.ANCHO_PANEL)
        piz.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        piz.grid_propagate(False)
        piz.columnconfigure(1, weight=1)
        self._piz = piz

        ttk.Label(piz, text=nombre, style="Tit.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(12, 4)
        )
        ttk.Separator(piz, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=4
        )

        # Subclase rellena inputs a partir de fila 2
        self._crear_inputs(piz)

        btn_calc = ttk.Button(
            piz, text="⚙  CALCULAR", style="Acc.TButton",
            command=self._calcular
        )
        btn_calc.grid(
            row=self._fila_boton(), column=0, columnspan=2,
            sticky="ew", padx=10, pady=(14, 6)
        )
        tip(btn_calc, "Ejecuta el modelo EOQ con los parámetros ingresados\n"
                      "y muestra la cantidad óptima de pedido (Q*), costos,\n"
                      "gráfica de inventario y calendario de pedidos.")

        # ── Sección de integración con Pedidos (solo en modo compras) ────────
        if self._pedidos_mode:
            self._build_pedidos_integration(piz)

        # ── Panel derecho ────────────────────────────────────────────────────
        pder = ttk.Frame(self)
        pder.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        pder.rowconfigure(0, weight=1)
        pder.columnconfigure(0, weight=1)

        nb = ttk.Notebook(pder)
        nb.grid(row=0, column=0, sticky="nsew")
        self._nb_out = nb

        # Sub-pestaña: Inventario
        self._t_inv = ttk.Frame(nb)
        nb.add(self._t_inv, text="📈  Inventario")
        self._t_inv.rowconfigure(0, weight=1)
        self._t_inv.columnconfigure(0, weight=1)

        # Sub-pestaña: Calendario
        self._t_cal = ttk.Frame(nb)
        nb.add(self._t_cal, text="📅  Calendario")
        self._t_cal.rowconfigure(0, weight=1)
        self._t_cal.columnconfigure(0, weight=1)

        # Sub-pestaña: Resultados
        self._t_res = ttk.Frame(nb)
        nb.add(self._t_res, text="📊  Resultados")
        self._t_res.rowconfigure(0, weight=1)
        self._t_res.columnconfigure(0, weight=1)

        # Sub-pestaña: Sensibilidad
        self._t_sen = ttk.Frame(nb)
        nb.add(self._t_sen, text="🔎  Sensibilidad")
        self._t_sen.rowconfigure(0, weight=1)
        self._t_sen.columnconfigure(0, weight=1)

        # Área de texto (Resultados)
        self._txt = tk.Text(
            self._t_res, font=F_MONO,
            bg=C["bg"], fg=C["texto"],
            relief="flat", state="disabled",
            padx=14, pady=12,
        )
        self._txt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(self._t_res, command=self._txt.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._txt["yscrollcommand"] = sb.set

        self._escribir("Ingrese los parámetros y presione  ⚙ CALCULAR.\n")

    # ── Métodos que las subclases sobreescriben ───────────────────────────────

    def _crear_inputs(self, piz):
        pass

    def _fila_boton(self):
        return 20

    def _calcular(self):
        pass

    # ── Integración Pedidos: selector SKU + botón «Crear Pedido» ─────────────

    def _build_pedidos_integration(self, piz):
        """
        Añade, debajo del botón CALCULAR, el bloque de integración con
        Pedidos: selector de SKU, info de stock/SS/LT y botón Crear Pedido.
        """
        base_row = self._fila_boton() + 1

        ttk.Separator(piz, orient="horizontal").grid(
            row=base_row, column=0, columnspan=2,
            sticky="ew", padx=10, pady=(6, 4)
        )
        lbl_sec = ttk.Label(
            piz, text="🔗  Aplicar resultado a un Pedido", style="Sub.TLabel"
        )
        lbl_sec.grid(row=base_row + 1, column=0, columnspan=2,
                     sticky="w", padx=10, pady=(0, 2))
        tip(lbl_sec,
            "Selecciona un SKU para auto-llenar lead time, precio e inventario\n"
            "de seguridad desde la base de datos. Luego calcula Q* y usa\n"
            "«Crear Pedido» para registrar el pedido óptimo directamente.")

        # Combobox de SKU
        ttk.Label(piz, text="SKU :", style="In.TLabel").grid(
            row=base_row + 2, column=0, sticky="w", padx=(10, 4), pady=2
        )
        self._skus_ped   = db.get_skus()
        sku_labels_ped   = ["(manual)"] + [
            f"{s['codigo']} — {s['descripcion']}" for s in self._skus_ped
        ]
        self._vSKU_ped   = tk.StringVar(value="(manual)")
        cb_sku = ttk.Combobox(
            piz, textvariable=self._vSKU_ped,
            values=sku_labels_ped, state="readonly", width=22
        )
        cb_sku.grid(row=base_row + 2, column=1, sticky="ew", padx=(0, 10), pady=2)
        cb_sku.bind("<<ComboboxSelected>>", self._on_sku_autofill)
        tip(cb_sku,
            "Elige un producto/materia prima para auto-llenar L (lead time),\n"
            "SS (inventario de seguridad) y P (precio) desde la BD.")

        # Label de info (stock / SS / LT)
        self._lbl_sku_info = ttk.Label(
            piz, text="", style="Dim.TLabel", wraplength=280
        )
        self._lbl_sku_info.grid(
            row=base_row + 3, column=0, columnspan=2,
            sticky="w", padx=10, pady=(0, 4)
        )

        # Botón Crear Pedido
        self._btn_crear_ped = ttk.Button(
            piz, text="✅  Crear Pedido con Q*",
            command=self._crear_pedido_con_qstar,
            state="disabled"
        )
        self._btn_crear_ped.grid(
            row=base_row + 4, column=0, columnspan=2,
            sticky="ew", padx=10, pady=(4, 8)
        )
        tip(self._btn_crear_ped,
            "Abre el formulario de nuevo pedido con la cantidad Q* calculada\n"
            "pre-cargada. Requiere haber presionado ⚙ CALCULAR primero.\n"
            "Si seleccionaste un SKU arriba, también se pre-llenará el producto.")

    def _on_sku_autofill(self, _=None):
        """Auto-llena L, SS, P desde el SKU seleccionado en el combobox."""
        sel = self._vSKU_ped.get()
        if sel == "(manual)" or not sel:
            self._lbl_sku_info.config(text="")
            return

        # Buscar el SKU correspondiente
        skus_lbl = ["(manual)"] + [
            f"{s['codigo']} — {s['descripcion']}" for s in self._skus_ped
        ]
        if sel not in skus_lbl:
            return
        idx = skus_lbl.index(sel) - 1
        sku = self._skus_ped[idx]

        # Stock de seguridad
        cons_list = db.get_consumibles()
        cons = next((c for c in cons_list if c["sku_id"] == sku["id"]), None)
        ss   = cons["stock_seguridad"] if cons else 0

        # Lead time del proveedor principal
        lt  = 0
        pid = sku.get("proveedor_principal_id")
        if pid:
            prov = db.get_proveedor(pid)
            if prov:
                lt = prov.get("lead_time", 0)

        # Precio: intentar proveedor principal, si no precio_venta
        precio = sku.get("precio_venta", 0) or 0
        if pid:
            sp_list = db.get_sku_proveedores(sku["id"])
            for sp in sp_list:
                if sp["proveedor_id"] == pid and sp["precio_proveedor"]:
                    precio = sp["precio_proveedor"]; break

        # Auto-llenar campos del modelo (si existen en la subclase)
        for attr, val in [("vL", lt), ("vSS", ss), ("vP", precio)]:
            if hasattr(self, attr):
                getattr(self, attr).set(str(val))

        stock = sku.get("stock_actual", 0)
        self._lbl_sku_info.config(
            text=f"Stock: {stock:.0f} u  ·  SS: {ss:.0f} u  ·  LT: {lt} días"
        )

    def _crear_pedido_con_qstar(self):
        """Abre el diálogo de nuevo pedido con Q* pre-cargado."""
        if not self._last_result:
            messagebox.showwarning(
                "Sin cálculo",
                "Primero presione ⚙ CALCULAR para obtener Q*."
            ); return

        Q = (self._last_result.get("Q_optimo")
             or self._last_result.get("Q Factible", 0))
        if not Q:
            messagebox.showwarning("Sin Q*", "No se encontró Q* en el resultado."); return

        # Obtener SKU seleccionado (si hay uno)
        sku_id = None
        sel = self._vSKU_ped.get()
        if sel and sel != "(manual)":
            skus_lbl = ["(manual)"] + [
                f"{s['codigo']} — {s['descripcion']}" for s in self._skus_ped
            ]
            if sel in skus_lbl:
                sku_id = self._skus_ped[skus_lbl.index(sel) - 1]["id"]

        # Importar y abrir el diálogo de pedido
        from tab_pedidos import _PedidoDialog
        pre = {"cantidad": round(Q, 2)}
        if sku_id:
            pre["sku_id"] = sku_id

        dlg = _PedidoDialog(self.winfo_toplevel(), pre)
        res = dlg.wait()
        if res:
            try:
                db.add_pedido(**res)
                messagebox.showinfo(
                    "Pedido creado",
                    f"✅ Pedido creado con Q* = {Q:.2f} unidades."
                )
            except Exception as e:
                messagebox.showerror("Error al crear pedido", str(e))

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _escribir(self, texto):
        self._txt.config(state="normal")
        self._txt.delete("1.0", tk.END)
        self._txt.insert(tk.END, texto)
        self._txt.config(state="disabled")

    def _limpiar_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _cerrar_fig(self):
        if self._fig is not None:
            plt.close(self._fig)
            self._fig = None

    def _habilitar_btn_crear(self):
        """Habilita el botón «Crear Pedido» si está en modo pedidos."""
        if self._pedidos_mode and hasattr(self, "_btn_crear_ped"):
            self._btn_crear_ped.config(state="normal")

    # ── Gráfica de inventario ─────────────────────────────────────────────────

    def _graficar_inventario(self, t, inv, titulo, lineas_extra=None):
        """
        Dibuja la curva de inventario en self._t_inv.

        lineas_extra : [(valor, color, label, linestyle), ...]
        """
        self._cerrar_fig()
        self._limpiar_frame(self._t_inv)

        fig, ax = plt.subplots(figsize=(8, 4.4))
        fig.patch.set_facecolor(C["graf_bg"])
        ax.set_facecolor(C["graf_bg"])

        ax.plot(t, inv, color=C["inv"], linewidth=1.9, label="Nivel de inventario")
        ax.fill_between(t, inv, alpha=0.12, color=C["inv"])

        if lineas_extra:
            for val, color, lbl, ls in lineas_extra:
                ax.axhline(y=val, color=color, linestyle=ls,
                           linewidth=1.3, label=lbl)

        ax.set_title(titulo, color=C["texto"], fontsize=11, pad=10)
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

        canvas = FigureCanvasTkAgg(fig, master=self._t_inv)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        frm_tb = ttk.Frame(self._t_inv)
        frm_tb.grid(row=1, column=0, sticky="ew")
        NavigationToolbar2Tk(canvas, frm_tb)

        self._fig = fig

    # ── Tabla / Calendario ────────────────────────────────────────────────────

    def _mostrar_calendario(self, df):
        self._limpiar_frame(self._t_cal)

        frm = ttk.Frame(self._t_cal)
        frm.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        cols = list(df.columns)
        tv = ttk.Treeview(frm, columns=cols, show="headings",
                          style="Cal.Treeview")
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=130, anchor="center", minwidth=80)
        for _, row in df.iterrows():
            tv.insert("", tk.END, values=list(row))

        tv.grid(row=0, column=0, sticky="nsew")
        sb_v = ttk.Scrollbar(frm, orient="vertical", command=tv.yview)
        sb_v.grid(row=0, column=1, sticky="ns")
        tv.configure(yscrollcommand=sb_v.set)
        sb_h = ttk.Scrollbar(frm, orient="horizontal", command=tv.xview)
        sb_h.grid(row=1, column=0, sticky="ew")
        tv.configure(xscrollcommand=sb_h.set)

        frm_btn = ttk.Frame(self._t_cal)
        frm_btn.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(frm_btn, text="💾  Exportar CSV",
                   command=lambda: self._exportar_csv(df)).pack(side="right", padx=4)

    def _exportar_csv(self, df):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            title="Guardar calendario",
        )
        if path:
            df.to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Archivo guardado en:\n{path}")

    # ── Análisis de sensibilidad ──────────────────────────────────────────────

    def _graficar_sensibilidad(self, modelo):
        self._limpiar_frame(self._t_sen)

        if not hasattr(modelo, "analisis_sensibilidad"):
            ttk.Label(
                self._t_sen,
                text="Análisis de sensibilidad no disponible para este modelo.",
                style="In.TLabel",
            ).pack(padx=20, pady=30)
            return

        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        fig.patch.set_facecolor(C["graf_bg"])
        fig.suptitle("Análisis de Sensibilidad — Q* y Costo Total",
                     color=C["texto"], fontsize=12)

        params = [
            ("D", "Demanda (D)",       "#3498db"),
            ("S", "Costo de Pedido (S)","#27ae60"),
            ("H", "Costo Mant. (H)",   "#e67e22"),
        ]

        for ax, (p, label, color) in zip(axes, params):
            vals, Q_v, C_v = modelo.analisis_sensibilidad(param=p)
            ax.set_facecolor(C["graf_bg"])
            ax2 = ax.twinx()

            l1, = ax.plot(vals, Q_v, color=color, linewidth=2, label="Q*")
            l2, = ax2.plot(vals, C_v, color="#e74c3c", linewidth=2,
                           linestyle="--", label="Costo Total")

            val_actual = getattr(modelo, p, None)
            if val_actual:
                ax.axvline(x=val_actual, color="white",
                           linestyle=":", alpha=0.5, linewidth=1.2)

            ax.set_title(label, color=C["texto"], fontsize=10)
            ax.set_xlabel("Valor del parámetro", color=C["dim"], fontsize=8)
            ax.set_ylabel("Q*", color=color, fontsize=8)
            ax2.set_ylabel("Costo Total ($)", color="#e74c3c", fontsize=8)
            ax.tick_params(colors=C["dim"])
            ax2.tick_params(colors="#e74c3c")
            ax.grid(True, color=C["grid"], alpha=0.4, linestyle="--")
            for sp in ax.spines.values():
                sp.set_color(C["grid"])
            ax.legend([l1, l2], ["Q*", "Costo Total"],
                      fontsize=8, facecolor=C["panel"],
                      labelcolor=C["texto"], edgecolor=C["grid"])

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self._t_sen)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")


# ─── Pestaña 1: EOQ Clásico ───────────────────────────────────────────────────

class TabEOQClasico(TabBase):

    def __init__(self, parent, pedidos_mode: bool = False):
        super().__init__(parent, "📦  EOQ Clásico", pedidos_mode)

    def _crear_inputs(self, f):
        ttk.Label(f, text="Parámetros del Modelo", style="Sub.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2)
        )
        self.vD   = _entry_row(f, "Demanda anual (D) :",       1000,  3)
        self.vS   = _entry_row(f, "Costo por pedido (S) :",      50,  4)
        self.vH   = _entry_row(f, "Costo mant./u./año (H) :",     2,  5)
        self.vP   = _entry_row(f, "Precio unitario (P) :",        10,  6)
        self.vL   = _entry_row(f, "Lead time (días) :",            7,  7)
        self.vSS  = _entry_row(f, "Inv. seguridad (SS) :",         0,  8)

        ttk.Separator(f, orient="horizontal").grid(
            row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=6
        )
        ttk.Label(f, text="Proyección", style="Sub.TLabel").grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10
        )
        self.vDias = _entry_row(f, "Días a graficar :",  365, 11)
        self.vAnos = _entry_row(f, "Años del calendario:", 1, 12)

    def _fila_boton(self): return 13

    def _calcular(self):
        try:
            D    = _flt(self.vD,   "Demanda",      0.01)
            S    = _flt(self.vS,   "Costo pedido", 0.01)
            H    = _flt(self.vH,   "Costo mant.",  0.01)
            P    = _flt(self.vP,   "Precio",       0)
            L    = _flt(self.vL,   "Lead time",    0)
            SS   = _flt(self.vSS,  "SS",           0)
            dias = int(_flt(self.vDias, "Días", 1))
            anos = int(_flt(self.vAnos, "Años", 1))
        except ValueError as e:
            messagebox.showerror("Error de entrada", str(e)); return

        m = InventarioEOQ(D, S, H, P, L, SS)
        r = m.calcular_costos()
        self._last_result = r
        self._habilitar_btn_crear()

        t, inv = m.serie_inventario(dias)
        extras = []
        if SS > 0:
            extras.append((SS, C["ss"],  f"Inv. Seguridad (SS={SS:.0f})", "--"))
        extras.append((r["punto_reorden"], C["rop"],
                       f"ROP = {r['punto_reorden']:.1f} u", ":"))
        self._graficar_inventario(
            t, inv, f"EOQ Clásico — Q* = {r['Q_optimo']:.1f} u", extras
        )

        sep = "─" * 44
        self._escribir(
            f"  {'RESULTADOS EOQ CLÁSICO':^42}\n  {sep}\n\n"
            f"  {'Cantidad óptima (Q*)':.<32}{r['Q_optimo']:>10.2f}  u\n"
            f"  {'Núm. pedidos / año':.<32}{r['num_pedidos_anio']:>10.2f}\n"
            f"  {'Tiempo de ciclo':.<32}{r['tiempo_ciclo_dias']:>10.2f}  días\n"
            f"  {'Punto de reorden (ROP)':.<32}{r['punto_reorden']:>10.2f}  u\n"
            f"  {'Inventario promedio':.<32}{r['inventario_promedio']:>10.2f}  u\n\n"
            f"  {sep}\n  COSTOS ANUALES\n  {sep}\n\n"
            f"  {'Costo de pedidos':.<32}$ {r['costo_pedidos']:>10.2f}\n"
            f"  {'Costo de mantenimiento':.<32}$ {r['costo_mantenimiento']:>10.2f}\n"
            f"  {'Costo de compra':.<32}$ {r['costo_compra']:>10.2f}\n"
            f"  {sep}\n"
            f"  {'COSTO TOTAL':.<32}$ {r['costo_total']:>10.2f}\n"
        )

        self._mostrar_calendario(m.generar_calendario(num_periodos=anos))
        self._graficar_sensibilidad(m)
        self._nb_out.select(0)


# ─── Pestaña 2: EOQ con Faltantes ─────────────────────────────────────────────

class TabEOQFaltantes(TabBase):

    def __init__(self, parent, pedidos_mode: bool = False):
        super().__init__(parent, "⚠  EOQ con Faltantes", pedidos_mode)

    def _crear_inputs(self, f):
        ttk.Label(f, text="Parámetros del Modelo", style="Sub.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2)
        )
        self.vD  = _entry_row(f, "Demanda anual (D) :",         1000, 3)
        self.vS  = _entry_row(f, "Costo por pedido (S) :",        50, 4)
        self.vH  = _entry_row(f, "Costo mant./u./año (H) :",       2, 5)
        self.vB  = _entry_row(f, "Costo faltante/u/año (B) :",     5, 6)
        self.vP  = _entry_row(f, "Precio unitario (P) :",          10, 7)
        self.vL  = _entry_row(f, "Lead time (días) :",              7, 8)

        ttk.Separator(f, orient="horizontal").grid(
            row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=6
        )
        ttk.Label(f, text="ℹ  B < H → muchos faltantes", style="Dim.TLabel").grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10
        )
        self.vDias = _entry_row(f, "Días a graficar :",  365, 11)
        self.vAnos = _entry_row(f, "Años del calendario:", 1, 12)

    def _fila_boton(self): return 13

    def _calcular(self):
        try:
            D    = _flt(self.vD,   "Demanda",        0.01)
            S    = _flt(self.vS,   "Costo pedido",   0.01)
            H    = _flt(self.vH,   "Costo mant.",    0.01)
            B    = _flt(self.vB,   "Costo faltante", 0.01)
            P    = _flt(self.vP,   "Precio",         0)
            L    = _flt(self.vL,   "Lead time",      0)
            dias = int(_flt(self.vDias, "Días", 1))
            anos = int(_flt(self.vAnos, "Años", 1))
        except ValueError as e:
            messagebox.showerror("Error de entrada", str(e)); return

        m = EOQFaltantes(D, S, H, B, P, L)
        r = m.calcular_costos()
        self._last_result = r
        self._habilitar_btn_crear()

        t, inv = m.serie_inventario(dias)
        self._graficar_inventario(
            t, inv,
            f"EOQ con Faltantes — Q*={r['Q_optimo']:.1f}, S*={r['inventario_maximo']:.1f} u",
            [
                (r["inventario_maximo"], C["verde"],
                 f"Inv. Máx. S*={r['inventario_maximo']:.1f}", "--"),
                (0, C["ss"], "Nivel cero (faltantes)", ":"),
            ],
        )

        sep = "─" * 44
        self._escribir(
            f"  {'RESULTADOS EOQ CON FALTANTES':^42}\n  {sep}\n\n"
            f"  {'Cantidad óptima (Q*)':.<32}{r['Q_optimo']:>10.2f}  u\n"
            f"  {'Inventario máximo (S*)':.<32}{r['inventario_maximo']:>10.2f}  u\n"
            f"  {'Faltante máximo':.<32}{r['faltante_maximo']:>10.2f}  u\n"
            f"  {'Núm. pedidos / año':.<32}{r['num_pedidos_anio']:>10.2f}\n"
            f"  {'Tiempo de ciclo':.<32}{r['tiempo_ciclo_dias']:>10.2f}  días\n"
            f"  {'T1 (con inventario)':.<32}{r['t1_inventario_dias']:>10.2f}  días\n"
            f"  {'T2 (con faltante)':.<32}{r['t2_faltante_dias']:>10.2f}  días\n\n"
            f"  {sep}\n  COSTOS ANUALES\n  {sep}\n\n"
            f"  {'Costo de pedidos':.<32}$ {r['costo_pedidos']:>10.2f}\n"
            f"  {'Costo de mantenimiento':.<32}$ {r['costo_mantenimiento']:>10.2f}\n"
            f"  {'Costo de faltantes':.<32}$ {r['costo_faltantes']:>10.2f}\n"
            f"  {'Costo de compra':.<32}$ {r['costo_compra']:>10.2f}\n"
            f"  {sep}\n"
            f"  {'COSTO TOTAL':.<32}$ {r['costo_total']:>10.2f}\n"
        )

        self._mostrar_calendario(m.generar_calendario(num_periodos=anos))
        self._graficar_sensibilidad(m)
        self._nb_out.select(0)


# ─── Pestaña 3: Revisión Periódica ────────────────────────────────────────────

class TabRevisionPeriodica(TabBase):

    _NIVELES_Z = {
        "90% (z = 1.28)":  "1.28",
        "95% (z = 1.645)": "1.645",
        "99% (z = 2.326)": "2.326",
        "Manual":          "",
    }

    def __init__(self, parent, pedidos_mode: bool = False):
        super().__init__(parent, "🔄  Revisión Periódica", pedidos_mode)

    def _crear_inputs(self, f):
        ttk.Label(f, text="Parámetros del Modelo", style="Sub.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2)
        )
        self.vD     = _entry_row(f, "Demanda anual (D) :",          1000,  3)
        self.vS     = _entry_row(f, "Costo por revisión (S) :",       50,  4)
        self.vH     = _entry_row(f, "Costo mant./u./año (H) :",        2,  5)
        self.vSigma = _entry_row(f, "Desv. est. dem. diaria (σ) :",    5,  6)
        self.vL     = _entry_row(f, "Lead time (días) :",              7,  7)
        self.vP     = _entry_row(f, "Precio unitario (P) :",          10,  8)

        ttk.Separator(f, orient="horizontal").grid(
            row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=6
        )
        ttk.Label(f, text="Nivel de Servicio", style="Sub.TLabel").grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10
        )
        ttk.Label(f, text="Nivel de servicio :", style="In.TLabel").grid(
            row=11, column=0, sticky="w", padx=(10, 4), pady=4
        )
        self.vNivel = tk.StringVar(value="95% (z = 1.645)")
        cb = ttk.Combobox(f, textvariable=self.vNivel,
                          values=list(self._NIVELES_Z.keys()),
                          state="readonly", width=16)
        cb.grid(row=11, column=1, sticky="ew", padx=(0, 10), pady=4)
        cb.bind("<<ComboboxSelected>>", self._on_nivel)

        self.vZ    = _entry_row(f, "Valor z (manual) :", 1.645, 12)
        self.vDias = _entry_row(f, "Días a graficar :",    365, 13)
        self.vAnos = _entry_row(f, "Años del calendario:",   1, 14)

    def _on_nivel(self, _=None):
        v = self._NIVELES_Z.get(self.vNivel.get(), "")
        if v:
            self.vZ.set(v)

    def _fila_boton(self): return 15

    def _calcular(self):
        try:
            D     = _flt(self.vD,     "Demanda",    0.01)
            S     = _flt(self.vS,     "Costo rev.", 0.01)
            H     = _flt(self.vH,     "Costo man.", 0.01)
            sigma = _flt(self.vSigma, "σ",          0)
            L     = _flt(self.vL,     "Lead time",  0)
            P     = _flt(self.vP,     "Precio",     0)
            z     = _flt(self.vZ,     "z",          0)
            dias  = int(_flt(self.vDias, "Días", 1))
            anos  = int(_flt(self.vAnos, "Años", 1))
        except ValueError as e:
            messagebox.showerror("Error de entrada", str(e)); return

        m = RevisionPeriodica(D, S, H, sigma, z, L, P)
        r = m.calcular_costos()
        self._last_result = r
        self._habilitar_btn_crear()

        t, inv = m.serie_inventario(dias)
        self._graficar_inventario(
            t, inv,
            f"Revisión Periódica — T*={r['T_optimo_dias']:.1f} días, M={r['nivel_maximo_M']:.1f} u",
            [
                (r["nivel_maximo_M"],       C["verde"], f"M = {r['nivel_maximo_M']:.1f}", "--"),
                (r["inventario_seguridad"], C["ss"],    f"SS = {r['inventario_seguridad']:.1f}", ":"),
            ],
        )

        sep = "─" * 44
        self._escribir(
            f"  {'RESULTADOS REVISIÓN PERIÓDICA':^42}\n  {sep}\n\n"
            f"  {'Período óptimo (T*)':.<32}{r['T_optimo_dias']:>10.2f}  días\n"
            f"  {'Nivel máximo (M)':.<32}{r['nivel_maximo_M']:>10.2f}  u\n"
            f"  {'Inventario de seguridad (SS)':.<32}{r['inventario_seguridad']:>10.2f}  u\n"
            f"  {'Q esperado por período':.<32}{r['Q_esperado_por_periodo']:>10.2f}  u\n"
            f"  {'Núm. revisiones / año':.<32}{r['num_revisiones_anio']:>10.2f}\n\n"
            f"  {sep}\n  COSTOS ANUALES\n  {sep}\n\n"
            f"  {'Costo de revisiones/pedidos':.<32}$ {r['costo_pedidos']:>10.2f}\n"
            f"  {'Costo de mantenimiento':.<32}$ {r['costo_mantenimiento']:>10.2f}\n"
            f"  {'Costo de compra':.<32}$ {r['costo_compra']:>10.2f}\n"
            f"  {sep}\n"
            f"  {'COSTO TOTAL':.<32}$ {r['costo_total']:>10.2f}\n"
        )

        self._mostrar_calendario(m.generar_calendario(num_periodos=anos))
        self._graficar_sensibilidad(m)
        self._nb_out.select(0)


# ─── Pestaña 4: Inventario de Seguridad ──────────────────────────────────────

class TabInventarioSeguridad(TabBase):

    _NIVELES_Z = {
        "90% (z = 1.28)":  "1.28",
        "95% (z = 1.645)": "1.645",
        "99% (z = 2.326)": "2.326",
        "Manual":          "",
    }

    def __init__(self, parent, pedidos_mode: bool = False):
        super().__init__(parent, "🛡  Inv. Seguridad (Rev. Continua)", pedidos_mode)

    def _crear_inputs(self, f):
        ttk.Label(f, text="Parámetros del Modelo", style="Sub.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2)
        )
        self.vD     = _entry_row(f, "Demanda anual (D) :",          1000,  3)
        self.vS     = _entry_row(f, "Costo por pedido (S) :",         50,  4)
        self.vH     = _entry_row(f, "Costo mant./u./año (H) :",        2,  5)
        self.vSigma = _entry_row(f, "Desv. est. dem. diaria (σ) :",    5,  6)
        self.vL     = _entry_row(f, "Lead time (días) :",              7,  7)
        self.vP     = _entry_row(f, "Precio unitario (P) :",          10,  8)

        ttk.Separator(f, orient="horizontal").grid(
            row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=6
        )
        ttk.Label(f, text="Nivel de Servicio", style="Sub.TLabel").grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10
        )
        ttk.Label(f, text="Nivel de servicio :", style="In.TLabel").grid(
            row=11, column=0, sticky="w", padx=(10, 4), pady=4
        )
        self.vNivel = tk.StringVar(value="95% (z = 1.645)")
        cb = ttk.Combobox(f, textvariable=self.vNivel,
                          values=list(self._NIVELES_Z.keys()),
                          state="readonly", width=16)
        cb.grid(row=11, column=1, sticky="ew", padx=(0, 10), pady=4)
        cb.bind("<<ComboboxSelected>>", self._on_nivel)

        self.vZ    = _entry_row(f, "Valor z (manual) :", 1.645, 12)
        self.vDias = _entry_row(f, "Días a graficar :",    365, 13)
        self.vAnos = _entry_row(f, "Años del calendario:",   1, 14)

    def _on_nivel(self, _=None):
        v = self._NIVELES_Z.get(self.vNivel.get(), "")
        if v:
            self.vZ.set(v)

    def _fila_boton(self): return 15

    def _calcular(self):
        try:
            D     = _flt(self.vD,     "Demanda",    0.01)
            S     = _flt(self.vS,     "Costo ped.", 0.01)
            H     = _flt(self.vH,     "Costo man.", 0.01)
            sigma = _flt(self.vSigma, "σ",          0)
            L     = _flt(self.vL,     "Lead time",  0)
            P     = _flt(self.vP,     "Precio",     0)
            z     = _flt(self.vZ,     "z",          0)
            dias  = int(_flt(self.vDias, "Días", 1))
            anos  = int(_flt(self.vAnos, "Años", 1))
        except ValueError as e:
            messagebox.showerror("Error de entrada", str(e)); return

        m = InventarioSeguridadContinuo(D, S, H, sigma, z, L, P)
        r = m.calcular_costos()
        self._last_result = r
        self._habilitar_btn_crear()

        t, inv = m.serie_inventario(dias)
        self._graficar_inventario(
            t, inv,
            f"Rev. Continua + SS — Q*={r['Q_optimo']:.1f}, SS={r['inventario_seguridad']:.1f} u",
            [
                (r["inventario_seguridad"], C["ss"],
                 f"SS = {r['inventario_seguridad']:.1f} u", "--"),
                (r["punto_reorden"], C["rop"],
                 f"ROP = {r['punto_reorden']:.1f} u", ":"),
            ],
        )

        sep = "─" * 44
        self._escribir(
            f"  {'RESULTADOS INV. SEGURIDAD (REV. CONT.)':^42}\n  {sep}\n\n"
            f"  {'Cantidad óptima (Q*)':.<32}{r['Q_optimo']:>10.2f}  u\n"
            f"  {'Inventario de seguridad (SS)':.<32}{r['inventario_seguridad']:>10.2f}  u\n"
            f"  {'Punto de reorden (ROP)':.<32}{r['punto_reorden']:>10.2f}  u\n"
            f"  {'σ durante lead time (σ_L)':.<32}{r['sigma_lead_time']:>10.2f}  u\n"
            f"  {'Factor de servicio (z)':.<32}{r['nivel_servicio_z']:>10.3f}\n"
            f"  {'Núm. pedidos / año':.<32}{r['num_pedidos_anio']:>10.2f}\n"
            f"  {'Tiempo de ciclo':.<32}{r['tiempo_ciclo_dias']:>10.2f}  días\n"
            f"  {'Inventario promedio':.<32}{r['inventario_promedio']:>10.2f}  u\n\n"
            f"  {sep}\n  COSTOS ANUALES\n  {sep}\n\n"
            f"  {'Costo de pedidos':.<32}$ {r['costo_pedidos']:>10.2f}\n"
            f"  {'Costo de mantenimiento':.<32}$ {r['costo_mantenimiento']:>10.2f}\n"
            f"  {'Costo de compra':.<32}$ {r['costo_compra']:>10.2f}\n"
            f"  {sep}\n"
            f"  {'COSTO TOTAL':.<32}$ {r['costo_total']:>10.2f}\n"
        )

        self._mostrar_calendario(m.generar_calendario(num_periodos=anos))
        self._graficar_sensibilidad(m)
        self._nb_out.select(0)


# ─── Pestaña 5: Descuentos por Cantidad ──────────────────────────────────────

class TabDescuentos(TabBase):

    _DEFAULTS = [(0, 10.0), (50, 9.5), (100, 9.0), (200, 8.5), (500, 8.0)]

    def __init__(self, parent, pedidos_mode: bool = False):
        super().__init__(parent, "🏷  Descuentos por Cantidad", pedidos_mode)

    def _crear_inputs(self, f):
        ttk.Label(f, text="Parámetros Generales", style="Sub.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2)
        )
        self.vD    = _entry_row(f, "Demanda anual (D) :", 1000, 3)
        self.vS    = _entry_row(f, "Costo por pedido (S) :", 50, 4)
        self.vHpct = _entry_row(f, "Costo mant. (% precio):", 0.20, 5)

        ttk.Separator(f, orient="horizontal").grid(
            row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=6
        )
        ttk.Label(f, text="Tabla de Descuentos", style="Sub.TLabel").grid(
            row=7, column=0, columnspan=2, sticky="w", padx=10
        )
        ttk.Label(f, text="  Desde (u)      Precio ($)",
                  style="Dim.TLabel").grid(
            row=8, column=0, columnspan=2, sticky="w", padx=10
        )

        self._desc_vars = []
        for i, (min_q, precio) in enumerate(self._DEFAULTS):
            fr = ttk.Frame(f, style="Panel.TFrame")
            fr.grid(row=9 + i, column=0, columnspan=2, sticky="ew",
                    padx=10, pady=2)
            vmin  = tk.StringVar(value=str(min_q))
            vprec = tk.StringVar(value=str(precio))
            ttk.Label(fr, text=f"Rango {i+1}:", style="In.TLabel").pack(
                side="left", padx=(4, 6)
            )
            ttk.Entry(fr, textvariable=vmin,  width=7).pack(side="left", padx=2)
            ttk.Label(fr, text="→", style="Dim.TLabel").pack(side="left", padx=2)
            ttk.Entry(fr, textvariable=vprec, width=8).pack(side="left", padx=2)
            self._desc_vars.append((vmin, vprec))

        self.vDias = _entry_row(f, "Días a graficar :",   365, 15)
        self.vAnos = _entry_row(f, "Años del calendario:", 1,  16)

    def _fila_boton(self): return 17

    def _calcular(self):
        try:
            D     = _flt(self.vD,    "Demanda",    0.01)
            S     = _flt(self.vS,    "Costo ped.", 0.01)
            Hpct  = _flt(self.vHpct, "% Mant.",    0.001)
            dias  = int(_flt(self.vDias, "Días", 1))
            anos  = int(_flt(self.vAnos, "Años", 1))

            descuentos = []
            for vmin, vprec in self._desc_vars:
                mq = float(vmin.get().strip())
                pr = float(vprec.get().strip())
                if pr > 0:
                    descuentos.append((mq, pr))
            if len(descuentos) < 2:
                raise ValueError("Se necesitan al menos 2 rangos de descuento.")
        except ValueError as e:
            messagebox.showerror("Error de entrada", str(e)); return

        m   = DescuentosCantidad(D, S, Hpct, descuentos)
        df  = m.calcular_eoq_por_rango()
        opt = m.obtener_optimo()

        if opt is None:
            messagebox.showerror("Sin solución", "No se encontró Q factible.")
            return

        self._last_result = {"Q_optimo": opt["Q Factible"], "costo_total": opt["Costo Total"]}
        self._habilitar_btn_crear()

        # Gráfica doble: inventario + comparación de costos
        self._limpiar_frame(self._t_inv)
        self._cerrar_fig()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.4))
        fig.patch.set_facecolor(C["graf_bg"])

        # Subplot 1: inventario en el tiempo
        t, inv = m.serie_inventario(dias)
        ax1.set_facecolor(C["graf_bg"])
        ax1.plot(t, inv, color=C["inv"], linewidth=1.9)
        ax1.fill_between(t, inv, alpha=0.12, color=C["inv"])
        ax1.set_title(
            f"Inventario — Q*={opt['Q Factible']:.0f} u, P=${opt['Precio Unitario']:.2f}",
            color=C["texto"], fontsize=10
        )
        ax1.set_xlabel("Tiempo (días)", color=C["dim"], fontsize=9)
        ax1.set_ylabel("Unidades", color=C["dim"], fontsize=9)
        ax1.tick_params(colors=C["dim"])
        ax1.grid(True, color=C["grid"], alpha=0.5, linestyle="--")
        for sp in ax1.spines.values(): sp.set_color(C["grid"])
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        # Subplot 2: costo total por rango
        ax2.set_facecolor(C["graf_bg"])
        colores_b = [C["verde"] if r["Seleccionado"] else "#5d6d7e"
                     for _, r in df.iterrows()]
        labels_b  = [f"P=${r['Precio Unitario']:.2f}\nQ={r['Q Factible']:.0f}"
                     for _, r in df.iterrows()]
        costos_b  = df["Costo Total"].tolist()
        bars = ax2.bar(range(len(costos_b)), costos_b,
                       color=colores_b, edgecolor=C["grid"], linewidth=0.7)
        ax2.set_xticks(range(len(costos_b)))
        ax2.set_xticklabels(labels_b, fontsize=8, color=C["dim"])
        ax2.set_title("Costo Total por Rango de Precio",
                      color=C["texto"], fontsize=10)
        ax2.set_ylabel("Costo Total ($)", color=C["dim"], fontsize=9)
        ax2.tick_params(colors=C["dim"])
        ax2.grid(True, axis="y", color=C["grid"], alpha=0.5, linestyle="--")
        for sp in ax2.spines.values(): sp.set_color(C["grid"])
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        ymax = max(costos_b)
        for bar, costo in zip(bars, costos_b):
            ax2.text(bar.get_x() + bar.get_width() / 2.0,
                     costo + ymax * 0.01,
                     f"${costo:,.0f}", ha="center", va="bottom",
                     fontsize=8, color=C["texto"])

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._t_inv)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        frm_tb = ttk.Frame(self._t_inv)
        frm_tb.grid(row=1, column=0, sticky="ew")
        NavigationToolbar2Tk(canvas, frm_tb)
        self._fig = fig

        # Resultados
        sep = "─" * 44
        txt = (
            f"  {'RESULTADOS DESCUENTOS POR CANTIDAD':^42}\n  {sep}\n\n"
            f"  RANGO ÓPTIMO SELECCIONADO\n  {sep}\n\n"
            f"  {'Precio óptimo':.<32}$ {opt['Precio Unitario']:>10.2f}\n"
            f"  {'Q factible óptimo':.<32}  {opt['Q Factible']:>10.2f}  u\n"
            f"  {'Costo total mínimo':.<32}$ {opt['Costo Total']:>10.2f}\n\n"
            f"  {sep}\n  ANÁLISIS POR RANGO\n  {sep}\n\n"
        )
        for _, row in df.iterrows():
            marca = "  ◄ ÓPTIMO" if row["Seleccionado"] else ""
            txt += (
                f"  P=${row['Precio Unitario']:.2f}  "
                f"Rango:[{row['Rango Q Min']},{row['Rango Q Max']}]  "
                f"Q={row['Q Factible']:.0f}  "
                f"CT=${row['Costo Total']:,.2f}{marca}\n"
            )
        self._escribir(txt)

        # Tabla de rangos en Sensibilidad
        self._limpiar_frame(self._t_sen)
        ttk.Label(self._t_sen,
                  text="Análisis Completo por Rango de Descuento",
                  style="Sub.TLabel").grid(row=0, column=0, sticky="w",
                                           padx=10, pady=8)
        cols = [c for c in df.columns if c != "Seleccionado"]
        tv = ttk.Treeview(self._t_sen, columns=cols, show="headings",
                          style="Cal.Treeview", height=8)
        for col in cols:
            tv.heading(col, text=col)
            tv.column(col, width=110, anchor="center", minwidth=80)
        for _, row in df.iterrows():
            vals = [row[c] for c in cols]
            tag  = "opt" if row["Seleccionado"] else ""
            tv.insert("", tk.END, values=vals, tags=(tag,))
        tv.tag_configure("opt", background="#1a5c3a", foreground=C["texto"])
        tv.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._t_sen.rowconfigure(1, weight=1)
        self._t_sen.columnconfigure(0, weight=1)

        self._mostrar_calendario(m.generar_calendario(num_periodos=anos))
        self._nb_out.select(0)


# ─── Aplicación principal ─────────────────────────────────────────────────────

class EOQApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Sistema de Inventarios — Modelo EOQ y Variantes")
        root.geometry("1280x760")
        root.minsize(920, 600)

        self._estilos()
        self._header()
        self._notebook()
        self._statusbar()

    # ── Estilos ───────────────────────────────────────────────────────────────

    def _estilos(self):
        s = ttk.Style()
        s.theme_use("clam")
        self.root.configure(bg=C["bg"])

        # Frames
        s.configure(".",          background=C["bg"], foreground=C["texto"])
        s.configure("Panel.TFrame",   background=C["panel"])
        s.configure("TFrame",         background=C["bg"])

        # Labels
        s.configure("Tit.TLabel",  background=C["panel"],
                    foreground=C["texto"],  font=F_TITULO)
        s.configure("Sub.TLabel",  background=C["panel"],
                    foreground=C["verde"],  font=F_BOLD)
        s.configure("In.TLabel",   background=C["panel"],
                    foreground=C["texto"],  font=F_LABEL)
        s.configure("Dim.TLabel",  background=C["panel"],
                    foreground=C["dim"],    font=("Segoe UI", 9, "italic"))

        # Entry
        s.configure("In.TEntry",
                    fieldbackground=C["input_bg"],
                    foreground=C["texto"],
                    insertcolor=C["texto"])

        # Botón acción
        s.configure("Acc.TButton",
                    background=C["boton"], foreground="white",
                    font=F_BOTON, padding=8)
        s.map("Acc.TButton",
              background=[("active", C["boton_h"])])

        # Notebook
        s.configure("TNotebook",      background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=C["panel"], foreground=C["dim"],
                    font=F_LABEL, padding=(12, 6))
        s.map("TNotebook.Tab",
              background=[("selected", C["bg"])],
              foreground=[("selected", C["texto"])])

        # Treeview (calendario)
        s.configure("Cal.Treeview",
                    background=C["panel"], fieldbackground=C["panel"],
                    foreground=C["texto"], font=("Consolas", 9), rowheight=24)
        s.configure("Cal.Treeview.Heading",
                    background=C["input_bg"], foreground=C["verde"],
                    font=F_BOLD)
        s.map("Cal.Treeview",
              background=[("selected", C["boton"])],
              foreground=[("selected", "white")])

        # Separator
        s.configure("TSeparator", background=C["grid"])

        # Combobox
        s.configure("TCombobox",
                    fieldbackground=C["input_bg"],
                    background=C["input_bg"],
                    foreground=C["texto"],
                    selectbackground=C["boton"])

    # ── Header ────────────────────────────────────────────────────────────────

    def _header(self):
        h = tk.Frame(self.root, bg=C["panel"], height=54)
        h.pack(fill="x", side="top")
        h.pack_propagate(False)

        tk.Label(h, text="  📦  Sistema de Inventarios EOQ",
                 bg=C["panel"], fg=C["texto"],
                 font=("Segoe UI", 15, "bold")).pack(
            side="left", padx=16, pady=10)

        tk.Label(
            h,
            text="Catálogos → Inventario → Compras & EOQ → Producción → Calendario → Facturas  |  v2.1",
            bg=C["panel"], fg=C["dim"],
            font=F_SMALL,
        ).pack(side="right", padx=16, pady=10)

    # ── Notebook principal ────────────────────────────────────────────────────

    def _notebook(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=4)

        # 1. Catálogos (ex-Maestro): primera parada — definir productos y proveedores
        self._tab_maestro = TabMaestro(nb)
        nb.add(self._tab_maestro,
               text="  📋 Catálogos  ")

        # 2. Inventario: verificar stock antes de comprar
        self._tab_inventario = TabInventario(nb)
        nb.add(self._tab_inventario,
               text="  📦 Inventario  ")

        # 3. Compras & EOQ: crear pedidos y calcular cantidades óptimas
        self._tab_compras = TabCompras(nb)
        nb.add(self._tab_compras,
               text="  🛒 Compras & EOQ  ")

        # 4. Producción: planificación MPS y lista de materiales BOM
        self._tab_produccion = TabProduccion(nb)
        nb.add(self._tab_produccion,
               text="  🏭 Producción  ")

        # 5. Calendario: cronograma de pedidos y gráficas de ciclos
        self._tab_calendario = TabCalendario(nb)
        nb.add(self._tab_calendario,
               text="  📅 Calendario  ")

        # 6. Facturas: registro y seguimiento de facturas de compra
        self._tab_facturas = TabFacturas(nb)
        nb.add(self._tab_facturas,
               text="  🧾 Facturas  ")

        # Tooltip-descripción al cambiar de tab
        TAB_DESCS = [
            "📋 Catálogos — Gestiona SKUs, proveedores, clientes, consumibles y categorías.",
            "📦 Inventario — Consulta stock actual, revisa alertas y carga datos desde CSV.",
            "🛒 Compras & EOQ — Lista de pedidos de compra + calculadora de los 5 modelos EOQ.\n"
            "     Los modelos calculan Q* y permiten crear pedidos directamente desde los resultados.",
            "🏭 Producción — Plan Maestro de Producción (MPS) y Lista de Materiales (BOM) multi-nivel.",
            "📅 Calendario — Cronograma mensual de compras y gráficas de ciclos de demanda.",
            "🧾 Facturas — Registro de facturas de compra con ítems y métodos de pago.",
        ]

        def _on_tab_changed(_=None):
            idx = nb.index(nb.select())
            if 0 <= idx < len(TAB_DESCS):
                self._status_var.set("  " + TAB_DESCS[idx])

        nb.bind("<<NotebookTabChanged>>", _on_tab_changed)

    # ── Barra de estado ───────────────────────────────────────────────────────

    def _statusbar(self):
        sb = tk.Frame(self.root, bg=C["panel"], height=22)
        sb.pack(fill="x", side="bottom")
        self._status_var = tk.StringVar(
            value="  📋 Catálogos — Gestiona SKUs, proveedores, clientes y consumibles."
        )
        tk.Label(
            sb,
            textvariable=self._status_var,
            bg=C["panel"], fg=C["dim"], font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            sb,
            text="EOQ × 5 variantes  |  SQLite local  |  v2.1  ",
            bg=C["panel"], fg=C["dim"], font=("Segoe UI", 9),
        ).pack(side="right")


# ─── Pestaña de Compras: lista de pedidos + 5 modelos EOQ integrados ─────────

class TabCompras(ttk.Frame):
    """
    Agrupa la lista de pedidos y los 5 calculadores EOQ en un único notebook.

    Sub-pestañas:
      📃 Pedidos      — CRUD completo de órdenes de compra.
      📦 EOQ Clásico  — EOQ estándar con auto-llenado desde SKU.
      ⚠  EOQ Faltantes — EOQ con backorders permitidos.
      🔄 Rev. Periódica — Sistema de revisión periódica (Sistema P).
      🛡 Inv. Seguridad — Revisión continua con stock de seguridad.
      🏷 Descuentos    — EOQ con descuentos por volumen (all-units).
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew", padx=2, pady=(4, 2))

        # ── Lista de Pedidos ──────────────────────────────────────────────────
        self._t_pedidos = TabPedidos(nb)
        nb.add(self._t_pedidos, text="  📃 Pedidos  ")

        # ── Modelos EOQ con integración de pedidos ────────────────────────────
        eoq_items = [
            (TabEOQClasico,          "  📦 EOQ Clásico  "),
            (TabEOQFaltantes,        "  ⚠  EOQ Faltantes  "),
            (TabRevisionPeriodica,   "  🔄 Rev. Periódica  "),
            (TabInventarioSeguridad, "  🛡 Inv. Seguridad  "),
            (TabDescuentos,          "  🏷 Descuentos  "),
        ]
        for TabCls, titulo in eoq_items:
            t = TabCls(nb, pedidos_mode=True)
            nb.add(t, text=titulo)


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def main():
    if _HAS_TTKB:
        root = ttkb.Window(themename="darkly")
    else:
        root = tk.Tk()
    EOQApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

