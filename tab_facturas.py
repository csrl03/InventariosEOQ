"""
tab_facturas.py — Pestaña Facturas de Compra
=============================================
Permite registrar facturas de compra con múltiples productos.
Al confirmar una factura, el stock de los SKUs se actualiza automáticamente.

Campos por factura:
  • Número (auto: FAC-YYYY-NNNN)
  • Fecha
  • Proveedor
  • Método de pago
  • Notas
  • Ítems: SKU, cantidad, unidad, precio unitario, subtotal
  • Total (suma de ítems)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

import pandas as pd

import database as db
from gui_utils import (C, F_LABEL, F_BOLD, F_SMALL, F_MONO,
                       _entry_row, _flt, make_treeview, crud_toolbar, SimpleDialog, tip)


METODOS_PAGO = ["efectivo", "transferencia", "tarjeta_debito",
                "tarjeta_credito", "cheque", "credito_proveedor"]


# ═══════════════════════════════════════════════════════════════════════════════
# Diálogo para ítem de factura
# ═══════════════════════════════════════════════════════════════════════════════

class _ItemDialog(SimpleDialog):
    def __init__(self, parent, skus, data=None):
        self._data = data or {}
        self._skus = skus
        super().__init__(parent, "Ítem — " + ("Editar" if data else "Agregar"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="SKU :", style="In.TLabel").grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=3)
        self._sku_labels = [f"{s['codigo']}  {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar()
        cur_id = self._data.get("sku_id")
        if cur_id and cur_id in self._sku_ids:
            self.vSKU.set(self._sku_labels[self._sku_ids.index(cur_id)])
        elif self._sku_labels:
            self.vSKU.set(self._sku_labels[0])
        cb = ttk.Combobox(f, textvariable=self.vSKU, values=self._sku_labels,
                          state="readonly", width=30)
        cb.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=3)
        cb.bind("<<ComboboxSelected>>", self._autofill)

        self.vCantidad = _entry_row(f, "Cantidad :",        self._data.get("cantidad", 1),          1)
        self.vUnidad   = _entry_row(f, "Unidad :",          self._data.get("unidad", "unidad"),      2)
        self.vPrecio   = _entry_row(f, "Precio unitario :", self._data.get("precio_unitario", 0),   3)

        # Subtotal en tiempo real
        self.lbl_sub = ttk.Label(f, text="Subtotal : $ 0.00", style="Sub.TLabel")
        self.lbl_sub.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        self.vCantidad.trace_add("write", lambda *_: self._update_subtotal())
        self.vPrecio.trace_add("write",   lambda *_: self._update_subtotal())
        self._autofill()

    def _autofill(self, _=None):
        """Intenta auto-llenar precio y unidad desde sku_proveedor."""
        label = self.vSKU.get()
        if label not in self._sku_labels: return
        idx    = self._sku_labels.index(label)
        sku_id = self._sku_ids[idx]
        provs  = db.get_sku_proveedores(sku_id)
        if provs:
            self.vPrecio.set(str(provs[0]["precio_proveedor"]))
            self.vUnidad.set(provs[0]["unidad_compra"])
        else:
            sku = db.get_sku(sku_id)
            if sku:
                self.vUnidad.set(sku["unidad"])
        self._update_subtotal()

    def _update_subtotal(self):
        try:
            sub = float(self.vCantidad.get() or 0) * float(self.vPrecio.get() or 0)
            self.lbl_sub.config(text=f"Subtotal : $ {sub:,.2f}")
        except Exception:
            pass

    def _get_values(self):
        if not self._sku_ids:
            raise ValueError("No hay SKUs disponibles.")
        label = self.vSKU.get()
        idx   = self._sku_labels.index(label) if label in self._sku_labels else 0
        return {
            "sku_id":          self._sku_ids[idx],
            "cantidad":        _flt(self.vCantidad, "Cantidad", 0.01),
            "unidad":          self.vUnidad.get().strip() or "unidad",
            "precio_unitario": _flt(self.vPrecio,   "Precio",   0),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Ventana de Detalle de Factura (edición de ítems)
# ═══════════════════════════════════════════════════════════════════════════════

class _FacturaDetalleWindow(tk.Toplevel):
    """Ventana para ver/editar los ítems de una factura y confirmarla."""

    def __init__(self, parent, fac_id, on_close=None):
        super().__init__(parent)
        self._fac_id   = fac_id
        self._on_close = on_close
        fac = db.get_factura(fac_id)
        self.title(f"Factura {fac['numero']} — {fac['proveedor_nombre'] or 'Sin proveedor'}")
        self.geometry("760x520")
        self.configure(bg=C["bg"])
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._build(fac)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _build(self, fac):
        # ── Encabezado ────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["panel"], padx=10, pady=6)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(1, weight=1)

        ttk.Label(hdr, text=f"N°  {fac['numero']}",
                  style="Tit.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 16))
        ttk.Label(hdr, text=f"Fecha: {fac['fecha']}",
                  style="In.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(hdr, text=f"Proveedor: {fac['proveedor_nombre'] or '—'}",
                  style="In.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(hdr, text=f"Pago: {fac['metodo_pago']}",
                  style="Sub.TLabel").grid(row=1, column=1, sticky="w")
        if fac["notas"]:
            ttk.Label(hdr, text=f"Notas: {fac['notas']}",
                      style="Dim.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")

        # ── Toolbar ítems ─────────────────────────────────────────────────
        ctrl = ttk.Frame(self)
        ctrl.grid(row=1, column=0, sticky="ew", padx=6, pady=(6, 2))
        ttk.Button(ctrl, text="+ Agregar ítem", style="Acc.TButton",
                   command=self._agregar_item).pack(side="left", padx=4)
        ttk.Button(ctrl, text="✏ Editar ítem",
                   command=self._editar_item).pack(side="left", padx=4)
        ttk.Button(ctrl, text="✕ Quitar ítem",
                   command=self._quitar_item).pack(side="left", padx=4)
        ttk.Button(ctrl, text="💾 Exportar ítems",
                   command=self._exportar).pack(side="right", padx=4)

        # ── Tabla ítems ───────────────────────────────────────────────────
        COLS = ("ID", "Código SKU", "Descripción", "Cantidad", "Unidad",
                "Precio Unit.", "Subtotal")
        frm_tv, self._tv = make_treeview(self, COLS, height=12)
        frm_tv.grid(row=2, column=0, sticky="nsew", padx=6, pady=2)
        self._tv.column("ID",           width=40)
        self._tv.column("Código SKU",   width=100)
        self._tv.column("Descripción",  width=180)
        self._tv.column("Cantidad",     width=80)
        self._tv.column("Unidad",       width=70)
        self._tv.column("Precio Unit.", width=90)
        self._tv.column("Subtotal",     width=95)

        # ── Total + Confirmar ─────────────────────────────────────────────
        btm = ttk.Frame(self)
        btm.grid(row=3, column=0, sticky="ew", padx=6, pady=6)
        self._lbl_total = ttk.Label(btm, text="Total: $0.00", style="Tit.TLabel")
        self._lbl_total.pack(side="left", padx=8)
        ttk.Button(btm, text="✔ Confirmar y actualizar stock",
                   style="Acc.TButton",
                   command=self._confirmar_stock).pack(side="right", padx=6)
        ttk.Button(btm, text="Cerrar",
                   command=self._cerrar).pack(side="right", padx=4)

        self._refresh_items()

    def _refresh_items(self):
        self._tv.delete(*self._tv.get_children())
        items = db.get_factura_items(self._fac_id)
        for it in items:
            self._tv.insert("", "end", values=(
                it["id"],
                it["sku_codigo"] or "",
                it["sku_desc"] or "",
                it["cantidad"],
                it["unidad"],
                it["precio_unitario"],
                round(it["subtotal"], 2),
            ))
        fac = db.get_factura(self._fac_id)
        self._lbl_total.config(text=f"Total: ${fac['total']:,.2f}")

    def _agregar_item(self):
        skus = db.get_skus()
        if not skus:
            messagebox.showinfo("Sin SKUs", "Cree primero SKUs en el módulo Maestro."); return
        dlg = _ItemDialog(self, skus)
        res = dlg.wait()
        if res:
            db.add_factura_item(self._fac_id, **res)
            self._refresh_items()

    def _selected_item(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un ítem."); return None
        return self._tv.item(sel[0])["values"]

    def _editar_item(self):
        v = self._selected_item()
        if v is None: return
        skus = db.get_skus()
        sku_id = next((s["id"] for s in skus if s["codigo"] == v[1]), None)
        data = {"id": v[0], "sku_id": sku_id,
                "cantidad": v[3], "unidad": v[4], "precio_unitario": v[5]}
        dlg  = _ItemDialog(self, skus, data)
        res  = dlg.wait()
        if res:
            db.update_factura_item(v[0], **res)
            self._refresh_items()

    def _quitar_item(self):
        v = self._selected_item()
        if v is None: return
        if messagebox.askyesno("Confirmar", "¿Quitar este ítem de la factura?"):
            db.delete_factura_item(v[0])
            self._refresh_items()

    def _confirmar_stock(self):
        items = db.get_factura_items(self._fac_id)
        if not items:
            messagebox.showwarning("Vacía", "La factura no tiene ítems."); return
        if messagebox.askyesno("Confirmar",
                               "¿Confirmar factura y sumar cantidades al stock de cada SKU?\n"
                               "Esta acción no se puede deshacer automáticamente."):
            db.confirmar_factura_en_stock(self._fac_id)
            messagebox.showinfo("Listo",
                                "Stock actualizado correctamente.")
            self._cerrar()

    def _exportar(self):
        items = db.get_factura_items(self._fac_id)
        if not items:
            messagebox.showinfo("Sin ítems", "La factura está vacía."); return
        fac  = db.get_factura(self._fac_id)
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"factura_{fac['numero'].replace('-', '_')}.csv"
        )
        if path:
            pd.DataFrame(items).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Ítems exportados en:\n{path}")

    def _cerrar(self):
        self.grab_release()
        self.destroy()
        if self._on_close:
            self._on_close()


# ═══════════════════════════════════════════════════════════════════════════════
# Diálogo para crear/editar cabecera de factura
# ═══════════════════════════════════════════════════════════════════════════════

class _FacturaCabeceraDialog(SimpleDialog):

    def __init__(self, parent, data=None):
        self._data = data or {}
        super().__init__(parent, "Factura — " + ("Editar" if data else "Nueva"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        if self._data.get("numero"):
            ttk.Label(f, text=f"  N°  {self._data['numero']}",
                      style="Sub.TLabel").grid(
                row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))

        # Proveedor
        ttk.Label(f, text="Proveedor :", style="In.TLabel").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=3)
        self._provs      = db.get_proveedores()
        prov_labels      = ["(sin proveedor)"] + [p["nombre"] for p in self._provs]
        self._prov_ids   = [None]              + [p["id"]     for p in self._provs]
        self.vProv       = tk.StringVar()
        cur_id = self._data.get("proveedor_id")
        if cur_id and cur_id in self._prov_ids:
            self.vProv.set(prov_labels[self._prov_ids.index(cur_id)])
        else:
            self.vProv.set(prov_labels[0])
        ttk.Combobox(f, textvariable=self.vProv, values=prov_labels,
                     state="readonly", width=24).grid(
            row=1, column=1, sticky="ew", padx=(0, 10), pady=3)

        # Fecha
        self.vFecha = _entry_row(f, "Fecha (YYYY-MM-DD) :",
                                  self._data.get("fecha", datetime.now().strftime("%Y-%m-%d")), 2)

        # Método de pago
        ttk.Label(f, text="Método de pago :", style="In.TLabel").grid(
            row=3, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vMetodo = tk.StringVar(value=self._data.get("metodo_pago", "efectivo"))
        ttk.Combobox(f, textvariable=self.vMetodo, values=METODOS_PAGO,
                     state="readonly", width=20).grid(
            row=3, column=1, sticky="w", padx=(0, 10), pady=3)

        self.vNotas = _entry_row(f, "Notas :", self._data.get("notas", ""), 4)

    def _get_values(self):
        prov_label = self.vProv.get()
        prov_id    = None
        for i, p in enumerate(self._provs):
            if p["nombre"] == prov_label:
                prov_id = p["id"]; break
        fecha = self.vFecha.get().strip()
        if not fecha:
            raise ValueError("La fecha no puede estar vacía.")
        return {
            "proveedor_id": prov_id,
            "metodo_pago":  self.vMetodo.get(),
            "notas":        self.vNotas.get().strip(),
            "fecha":        fecha,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Tab Facturas principal
# ═══════════════════════════════════════════════════════════════════════════════

class TabFacturas(ttk.Frame):
    """
    Pestaña de Facturas de Compra.
    Lista facturas con resumen + botón para abrir detalle/ítems.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = crud_toolbar(
            self,
            on_add=self._nueva_factura,
            on_edit=self._editar_cabecera,
            on_delete=self._eliminar,
            extras=[("📄  Ver / Editar ítems", self._abrir_detalle)],
            tip_add="Registrar una nueva factura de compra con proveedor, fecha y método de pago.",
            tip_edit="Editar la cabecera de la factura seleccionada (fecha, proveedor, pago).",
            tip_del="Eliminar la factura seleccionada y todos sus ítems (acción irreversible).",
            tips_extras=["Abrir el detalle de ítems de la factura: agregar/quitar productos, cantidades y precios."],
        )
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        # ── Tabla ─────────────────────────────────────────────────────────
        COLS = ("ID", "N° Factura", "Fecha", "Proveedor",
                "Método Pago", "Total ($)", "Ítems", "Notas")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        self._tv.column("ID",           width=40)
        self._tv.column("N° Factura",   width=130)
        self._tv.column("Fecha",        width=90)
        self._tv.column("Proveedor",    width=160)
        self._tv.column("Método Pago",  width=120)
        self._tv.column("Total ($)",    width=100)
        self._tv.column("Ítems",        width=55)
        self._tv.column("Notas",        width=180)

        self._tv.bind("<Double-1>", lambda _: self._abrir_detalle())

        # ── Resumen ───────────────────────────────────────────────────────
        self._lbl_resumen = ttk.Label(self, text="", style="Dim.TLabel")
        self._lbl_resumen.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 4))

        # ── Botón exportar ────────────────────────────────────────────────
        frm_btm = ttk.Frame(self)
        frm_btm.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 6))
        ttk.Button(frm_btm, text="💾 Exportar listado CSV",
                   command=self._exportar_lista).pack(side="right", padx=4)
        ttk.Button(frm_btm, text="🔄 Actualizar",
                   command=self.refresh).pack(side="left", padx=4)

        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        facturas    = db.get_facturas()
        total_gral  = 0
        for f in facturas:
            items      = db.get_factura_items(f["id"])
            n_items    = len(items)
            total_gral += f["total"]
            self._tv.insert("", "end", values=(
                f["id"], f["numero"], f["fecha"],
                f["proveedor_nombre"] or "",
                f["metodo_pago"],
                f"{f['total']:,.2f}",
                n_items,
                f["notas"],
            ))
        n = len(facturas)
        self._lbl_resumen.config(
            text=f"  {n} factura(s)  |  Total acumulado: ${total_gral:,.2f}")

    def _selected_id(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione una factura."); return None
        return self._tv.item(sel[0])["values"][0]

    def _selected_data(self):
        fac_id = self._selected_id()
        if fac_id is None: return None
        return db.get_factura(fac_id)

    def _nueva_factura(self):
        dlg = _FacturaCabeceraDialog(self.winfo_toplevel())
        res = dlg.wait()
        if res:
            try:
                fac_id = db.add_factura(**res)
                self.refresh()
                # Abrir detalle para agregar ítems inmediatamente
                _FacturaDetalleWindow(self.winfo_toplevel(), fac_id,
                                      on_close=self.refresh)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _editar_cabecera(self):
        data = self._selected_data()
        if not data: return
        dlg = _FacturaCabeceraDialog(self.winfo_toplevel(), data)
        res = dlg.wait()
        if res:
            try:
                # Solo actualizamos proveedor, fecha, método de pago y notas
                db.execute(
                    "UPDATE facturas SET proveedor_id=?,fecha=?,metodo_pago=?,notas=? WHERE id=?",
                    (res["proveedor_id"], res["fecha"], res["metodo_pago"],
                     res["notas"], data["id"])
                )
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _eliminar(self):
        fac_id = self._selected_id()
        if fac_id is None: return
        fac    = db.get_factura(fac_id)
        if messagebox.askyesno("Confirmar",
                               f"¿Eliminar factura {fac['numero']}?\n"
                               "Todos sus ítems también serán eliminados."):
            db.delete_factura(fac_id)
            self.refresh()

    def _abrir_detalle(self):
        fac_id = self._selected_id()
        if fac_id is None: return
        _FacturaDetalleWindow(self.winfo_toplevel(), fac_id,
                              on_close=self.refresh)

    def _exportar_lista(self):
        facturas = db.get_facturas()
        if not facturas:
            messagebox.showinfo("Sin datos", "No hay facturas registradas."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            title="Exportar listado de facturas"
        )
        if path:
            pd.DataFrame(facturas).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Facturas exportadas en:\n{path}")
