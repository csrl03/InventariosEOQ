"""
tab_pedidos.py — Pestaña de Pedidos de Compra
==============================================
Lista de todos los pedidos con CRUD completo.
La fecha de orden se guarda automáticamente al crear.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import database as db
from gui_utils import C, F_LABEL, F_BOLD, _entry_row, _flt, make_treeview, crud_toolbar, SimpleDialog, tip


# ─── Diálogo Pedido ───────────────────────────────────────────────────────────

class _PedidoDialog(SimpleDialog):
    ESTADOS = ["pendiente", "recibido", "cancelado"]

    def __init__(self, parent, data=None):
        self._data  = data or {}
        self._skus  = db.get_skus()
        self._provs = db.get_proveedores()
        super().__init__(parent, "Pedido — " + ("Editar" if data else "Nuevo"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        # SKU
        ttk.Label(f, text="SKU :", style="In.TLabel").grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=3)
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar()
        cur_sku = self._data.get("sku_id")
        if cur_sku and cur_sku in self._sku_ids:
            self.vSKU.set(self._sku_labels[self._sku_ids.index(cur_sku)])
        elif self._sku_labels:
            self.vSKU.set(self._sku_labels[0])
        cb_sku = ttk.Combobox(f, textvariable=self.vSKU, values=self._sku_labels,
                               state="readonly", width=28)
        cb_sku.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=3)
        cb_sku.bind("<<ComboboxSelected>>", self._on_sku_changed)

        # Proveedor
        ttk.Label(f, text="Proveedor :", style="In.TLabel").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=3)
        self._prov_labels = [p["nombre"] for p in self._provs]
        self._prov_ids    = [p["id"]     for p in self._provs]
        self.vProv = tk.StringVar()
        cur_prov = self._data.get("proveedor_id")
        if cur_prov and cur_prov in self._prov_ids:
            self.vProv.set(self._prov_labels[self._prov_ids.index(cur_prov)])
        elif self._prov_labels:
            self.vProv.set(self._prov_labels[0])
        self._cb_prov = ttk.Combobox(f, textvariable=self.vProv,
                                      values=self._prov_labels,
                                      state="readonly", width=22)
        self._cb_prov.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=3)
        self._cb_prov.bind("<<ComboboxSelected>>", self._on_prov_changed)

        # Precio (se auto-llena al seleccionar SKU+proveedor)
        self.vPrecio = _entry_row(f, "Precio unitario :", self._data.get("precio_unitario", 0), 2)

        self.vCantidad = _entry_row(f, "Cantidad :",         self._data.get("cantidad", 1),              3)
        self.vUnidad   = _entry_row(f, "Unidad :",           self._data.get("unidad", "unidad"),          4)
        self.vFechaEnt = _entry_row(f, "Entrega esperada :", self._data.get("fecha_entrega_esperada", ""), 5)

        ttk.Label(f, text="Estado :", style="In.TLabel").grid(
            row=6, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vEstado = tk.StringVar(value=self._data.get("estado", "pendiente"))
        ttk.Combobox(f, textvariable=self.vEstado, values=self.ESTADOS,
                     state="readonly", width=12).grid(
            row=6, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(f, text="ℹ  La fecha de orden se registra automáticamente.",
                  style="Dim.TLabel").grid(row=7, column=0, columnspan=2,
                                            sticky="w", padx=10, pady=(4, 0))

        self._try_autofill_precio()

    def _on_sku_changed(self, _=None):
        self._try_autofill_precio()

    def _on_prov_changed(self, _=None):
        self._try_autofill_precio()
        # Auto-fill unidad de compra
        sku_id  = self._get_sku_id()
        prov_id = self._get_prov_id()
        if sku_id and prov_id:
            sp_list = db.get_sku_proveedores(sku_id)
            for sp in sp_list:
                if sp["proveedor_id"] == prov_id and sp["unidad_compra"]:
                    self.vUnidad.set(sp["unidad_compra"]); break

    def _get_sku_id(self):
        if self.vSKU.get() in self._sku_labels:
            return self._sku_ids[self._sku_labels.index(self.vSKU.get())]
        return None

    def _get_prov_id(self):
        if self.vProv.get() in self._prov_labels:
            return self._prov_ids[self._prov_labels.index(self.vProv.get())]
        return None

    def _try_autofill_precio(self):
        sku_id  = self._get_sku_id()
        prov_id = self._get_prov_id()
        if sku_id and prov_id:
            sp_list = db.get_sku_proveedores(sku_id)
            for sp in sp_list:
                if sp["proveedor_id"] == prov_id:
                    self.vPrecio.set(str(sp["precio_proveedor"])); return

    def _get_values(self):
        sku_id  = self._get_sku_id()
        prov_id = self._get_prov_id()
        if not sku_id:
            raise ValueError("Seleccione un SKU.")
        return {
            "sku_id":                sku_id,
            "proveedor_id":          prov_id,
            "cantidad":              _flt(self.vCantidad, "Cantidad", 0.001),
            "unidad":                self.vUnidad.get().strip() or "unidad",
            "precio_unitario":       _flt(self.vPrecio,   "Precio",   0),
            "fecha_entrega_esperada": self.vFechaEnt.get().strip(),
            "estado":                self.vEstado.get(),
        }


# ─── Tab Pedidos ──────────────────────────────────────────────────────────────

class TabPedidos(ttk.Frame):

    COLS = ("ID", "Fecha Orden", "SKU", "Descripción SKU",
            "Proveedor", "Cantidad", "Unidad", "Precio Unit.",
            "Total", "Estado", "Entrega Esperada")

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        toolbar = crud_toolbar(
            self,
            on_add=self._add,
            on_edit=self._edit,
            on_delete=self._delete,
            extras=[
                ("✅  Marcar recibido", self._marcar_recibido),
                ("💾  Exportar CSV",    self._exportar),
            ],
            tip_add="Crear un nuevo pedido de compra: selecciona SKU, proveedor, cantidad y fecha esperada.",
            tip_edit="Editar el pedido seleccionado en la lista.",
            tip_del="Eliminar el pedido seleccionado (acción irreversible).",
            tips_extras=[
                "Cambiar estado del pedido a 'recibido' y actualizar el stock del SKU.",
                "Exportar la lista actual de pedidos a un archivo CSV.",
            ],
        )
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        frm_tv, self._tv = make_treeview(self, self.COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        self._tv.column("ID",            width=40,  minwidth=30)
        self._tv.column("Fecha Orden",   width=95)
        self._tv.column("SKU",           width=80)
        self._tv.column("Descripción SKU", width=160)
        self._tv.column("Proveedor",     width=140)
        self._tv.column("Cantidad",      width=80)
        self._tv.column("Unidad",        width=70)
        self._tv.column("Precio Unit.",  width=85)
        self._tv.column("Total",         width=90)
        self._tv.column("Estado",        width=85)
        self._tv.column("Entrega Esperada", width=110)

        # Colorear filas según estado
        self._tv.tag_configure("recibido",  background="#1a3a2a", foreground=C["texto"])
        self._tv.tag_configure("cancelado", background="#3a1a1a", foreground=C["dim"])
        self._tv.tag_configure("pendiente", background=C["panel"], foreground=C["texto"])

        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_pedidos():
            total = round(r["cantidad"] * r["precio_unitario"], 2)
            tag   = r["estado"]
            self._tv.insert("", "end", tags=(tag,), values=(
                r["id"], r["fecha_orden"],
                r["sku_codigo"] or "", r["sku_desc"] or "",
                r["proveedor_nombre"] or "",
                r["cantidad"], r["unidad"],
                r["precio_unitario"], total,
                r["estado"], r["fecha_entrega_esperada"]
            ))

    def _selected_id(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un pedido."); return None
        return self._tv.item(sel[0])["values"][0]

    def _selected_data(self):
        sel = self._tv.selection()
        if not sel: return None
        v = self._tv.item(sel[0])["values"]
        # Reconstruir sku_id y proveedor_id a partir de los nombres
        sku_id = prov_id = None
        for s in db.get_skus():
            if s["codigo"] == v[2]:
                sku_id = s["id"]; break
        for p in db.get_proveedores():
            if p["nombre"] == v[4]:
                prov_id = p["id"]; break
        return {
            "id": v[0], "fecha_orden": v[1],
            "sku_id": sku_id, "proveedor_id": prov_id,
            "cantidad": v[5], "unidad": v[6],
            "precio_unitario": v[7], "estado": v[9],
            "fecha_entrega_esperada": v[10]
        }

    def _add(self):
        dlg = _PedidoDialog(self.winfo_toplevel())
        res = dlg.wait()
        if res:
            try:
                db.add_pedido(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        data = self._selected_data()
        if not data: return
        dlg = _PedidoDialog(self.winfo_toplevel(), data)
        res = dlg.wait()
        if res:
            try:
                db.update_pedido(
                    data["id"],
                    res["sku_id"], res["proveedor_id"],
                    res["cantidad"], res["unidad"], res["precio_unitario"],
                    res["fecha_entrega_esperada"], res["estado"]
                )
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        ped_id = self._selected_id()
        if ped_id is None: return
        if messagebox.askyesno("Confirmar", "¿Eliminar este pedido?"):
            db.delete_pedido(ped_id)
            self.refresh()

    def _marcar_recibido(self):
        ped_id = self._selected_id()
        if ped_id is None: return
        db.marcar_recibido(ped_id)
        self.refresh()

    def _exportar(self):
        import pandas as pd
        pedidos = db.get_pedidos()
        if not pedidos:
            messagebox.showinfo("Sin datos", "No hay pedidos para exportar."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            title="Exportar pedidos"
        )
        if path:
            df = pd.DataFrame(pedidos)
            df.to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"Pedidos guardados en:\n{path}")
