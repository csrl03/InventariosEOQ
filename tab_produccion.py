"""
tab_produccion.py — Pestaña Producción: MPS + BOM Multi-nivel
=============================================================
Sub-pestañas:
  • MPS  — Plan Maestro de Producción (grilla período × SKU)
  • BOM  — Lista de Materiales multi-nivel con árbol visual + CRUD
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import pandas as pd

import database as db
from gui_utils import (C, F_LABEL, F_BOLD, F_MONO, F_SMALL,
                       _entry_row, _flt, _int, make_treeview,
                       crud_toolbar, SimpleDialog, tip)


# ═══════════════════════════════════════════════════════════════════════════════
# MPS — Plan Maestro de Producción
# ═══════════════════════════════════════════════════════════════════════════════

class _MPSCellDialog(SimpleDialog):
    """Editar cantidad planificada / real de un período."""

    def __init__(self, parent, sku_codigo, periodo, plan=0, real=0):
        self._sku_codigo = sku_codigo
        self._periodo    = periodo
        self._plan       = plan
        self._real       = real
        super().__init__(parent, f"MPS — {sku_codigo} | {periodo}")

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text=f"SKU: {self._sku_codigo}  |  Período: {self._periodo}",
                  style="Sub.TLabel").grid(row=0, column=0, columnspan=2,
                                            sticky="w", padx=10, pady=(0, 6))
        self.vPlan = _entry_row(f, "Cantidad planificada :", self._plan, 1)
        self.vReal = _entry_row(f, "Cantidad real :",        self._real, 2)

    def _get_values(self):
        return {
            "cantidad_planificada": _flt(self.vPlan, "Planificada", 0),
            "cantidad_real":        _flt(self.vReal, "Real",        0),
        }


class _TabMPS(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        # Controles superiores
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(ctrl, text="SKU :", style="In.TLabel").pack(side="left", padx=(4, 2))
        self._skus = db.get_skus()
        self._sku_labels = ["(todos)"] + [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [None] + [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar(value="(todos)")
        self._cb_sku = ttk.Combobox(ctrl, textvariable=self.vSKU,
                                     values=self._sku_labels, state="readonly", width=24)
        self._cb_sku.pack(side="left", padx=2)

        b_ref = ttk.Button(ctrl, text="🔄 Actualizar", command=self.refresh)
        b_ref.pack(side="left", padx=6)
        tip(b_ref, "Recargar el Plan Maestro de Producción desde la base de datos.")
        b_add = ttk.Button(ctrl, text="➕ Nuevo registro", style="Acc.TButton",
                   command=self._add_row)
        b_add.pack(side="left", padx=2)
        tip(b_add, "Agregar un registro de cantidad planificada o real para un SKU y período.")
        b_edit = ttk.Button(ctrl, text="✏ Editar celda", command=self._edit_row)
        b_edit.pack(side="left", padx=2)
        tip(b_edit, "Editar la cantidad planificada y real del registro seleccionado.")
        b_del = ttk.Button(ctrl, text="🗑 Eliminar", command=self._delete_row)
        b_del.pack(side="left", padx=2)
        tip(b_del, "Eliminar el registro de producción seleccionado.")
        b_exp = ttk.Button(ctrl, text="💾 Exportar CSV", command=self._exportar)
        b_exp.pack(side="right", padx=6)
        tip(b_exp, "Exportar el MPS completo a un archivo CSV.")

        # Treeview
        COLS = ("ID", "SKU", "Descripción", "Período", "Cant. Planificada", "Cant. Real")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        self.rowconfigure(1, weight=1)
        self._tv.column("ID",              width=40)
        self._tv.column("SKU",             width=90)
        self._tv.column("Descripción",     width=180)
        self._tv.column("Período",         width=80)
        self._tv.column("Cant. Planificada", width=120)
        self._tv.column("Cant. Real",      width=100)

        self.refresh()

    def refresh(self):
        self._skus = db.get_skus()
        self._sku_labels = ["(todos)"] + [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [None] + [s["id"] for s in self._skus]
        self._cb_sku["values"] = self._sku_labels

        sku_id = None
        if self.vSKU.get() in self._sku_labels:
            idx = self._sku_labels.index(self.vSKU.get())
            sku_id = self._sku_ids[idx]

        self._tv.delete(*self._tv.get_children())
        for r in db.get_mps(sku_id):
            self._tv.insert("", "end", values=(
                r["id"], r["codigo"], r["descripcion"],
                r["periodo"], r["cantidad_planificada"], r["cantidad_real"]
            ))

    def _selected_row(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un registro."); return None
        v = self._tv.item(sel[0])["values"]
        # Buscar sku_id
        sku_id = None
        for s in self._skus:
            if s["codigo"] == v[1]:
                sku_id = s["id"]; break
        return {"id": v[0], "sku_id": sku_id, "sku_codigo": v[1],
                "descripcion": v[2], "periodo": v[3],
                "cantidad_planificada": v[4], "cantidad_real": v[5]}

    def _add_row(self):
        dlg = _MPSAddDialog(self.winfo_toplevel(), db.get_skus())
        res = dlg.wait()
        if res:
            try:
                db.upsert_mps(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit_row(self):
        row = self._selected_row()
        if not row: return
        dlg = _MPSCellDialog(self.winfo_toplevel(),
                              row["sku_codigo"], row["periodo"],
                              row["cantidad_planificada"], row["cantidad_real"])
        res = dlg.wait()
        if res:
            try:
                db.upsert_mps(row["sku_id"], row["periodo"],
                               res["cantidad_planificada"], res["cantidad_real"])
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete_row(self):
        row = self._selected_row()
        if not row: return
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro del MPS?"):
            db.delete_mps(row["id"])
            self.refresh()

    def _exportar(self):
        rows = db.get_mps()
        if not rows:
            messagebox.showinfo("Sin datos", "No hay datos en el MPS."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            title="Exportar MPS"
        )
        if path:
            pd.DataFrame(rows).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"MPS guardado en:\n{path}")


class _MPSAddDialog(SimpleDialog):
    def __init__(self, parent, skus):
        self._skus = skus
        super().__init__(parent, "Nuevo Registro MPS")

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="SKU :", style="In.TLabel").grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=3)
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar(value=self._sku_labels[0] if self._sku_labels else "")
        ttk.Combobox(f, textvariable=self.vSKU, values=self._sku_labels,
                     state="readonly", width=26).grid(
            row=0, column=1, sticky="ew", padx=(0, 10), pady=3)

        self.vPeriodo = _entry_row(f, "Período (YYYY-MM) :", "", 1)
        self.vPlan    = _entry_row(f, "Cant. planificada :", 0,  2)
        self.vReal    = _entry_row(f, "Cant. real :",        0,  3)

    def _get_values(self):
        if not self._sku_ids:
            raise ValueError("No hay SKUs registrados.")
        periodo = self.vPeriodo.get().strip()
        if len(periodo) != 7 or periodo[4] != "-":
            raise ValueError("Período debe tener formato YYYY-MM (ej. 2026-01).")
        idx = self._sku_labels.index(self.vSKU.get()) if self.vSKU.get() in self._sku_labels else 0
        return {
            "sku_id":               self._sku_ids[idx],
            "periodo":              periodo,
            "cantidad_planificada": _flt(self.vPlan, "Planificada", 0),
            "cantidad_real":        _flt(self.vReal, "Real",        0),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# BOM — Lista de Materiales
# ═══════════════════════════════════════════════════════════════════════════════

class _BOMDialog(SimpleDialog):
    def __init__(self, parent, skus, data=None):
        self._data = data or {}
        self._skus = skus
        super().__init__(parent, "BOM — " + ("Editar" if data else "Nuevo componente"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        # ── Separar productos de materias / consumibles ───────────────────
        _TYPE_PREFIX = {
            "producto":      "🏷 ",
            "materia_prima": "[MAT] ",
            "consumible":    "[CONS] ",
        }

        productos   = [s for s in self._skus if s.get("tipo") == "producto"]
        componentes = sorted(
            [s for s in self._skus if s.get("tipo") in ("materia_prima", "consumible", "producto")],
            key=lambda s: (0 if s.get("tipo") == "materia_prima" else
                           1 if s.get("tipo") == "consumible" else 2)
        )

        def _lbl_prod(s):
            return f"{s['codigo']} — {s['descripcion']}"

        def _lbl_comp(s):
            prefix = _TYPE_PREFIX.get(s.get("tipo", ""), "")
            stock  = s.get("stock_actual", 0) or 0
            return f"{prefix}{s['codigo']} — {s['descripcion']}  (stock: {stock} u)"

        prod_labels = [_lbl_prod(s) for s in (productos or self._skus)]
        prod_ids    = [s["id"] for s in (productos or self._skus)]
        comp_labels = [_lbl_comp(s) for s in componentes]
        comp_ids    = [s["id"] for s in componentes]

        # ── Producto (artículo terminado) ─────────────────────────────────
        ttk.Label(f, text="Producto terminado :", style="In.TLabel").grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vProd = tk.StringVar()
        cur = self._data.get("producto_id")
        if cur and cur in prod_ids:
            self.vProd.set(prod_labels[prod_ids.index(cur)])
        elif prod_labels:
            self.vProd.set(prod_labels[0])
        ttk.Combobox(f, textvariable=self.vProd, values=prod_labels,
                     state="readonly", width=30).grid(
            row=0, column=1, sticky="ew", padx=(0, 10), pady=3)
        ttk.Label(f, text="Solo productos terminados", style="Dim.TLabel").grid(
            row=0, column=2, sticky="w", padx=(0, 6))

        # ── Componente (materia prima / consumible / semielaborado) ───────
        ttk.Label(f, text="Componente :", style="In.TLabel").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vComp = tk.StringVar()
        cur2 = self._data.get("componente_id")
        if cur2 and cur2 in comp_ids:
            self.vComp.set(comp_labels[comp_ids.index(cur2)])
        elif comp_labels:
            self.vComp.set(comp_labels[0])
        self._cb_comp = ttk.Combobox(f, textvariable=self.vComp, values=comp_labels,
                                      state="readonly", width=38)
        self._cb_comp.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=3)

        # Etiqueta de stock en tiempo real del componente seleccionado
        self._lbl_stock = ttk.Label(f, text="", style="Dim.TLabel")
        self._lbl_stock.grid(row=2, column=1, sticky="w", padx=(0, 10))

        def _on_comp_sel(_=None):
            v = self.vComp.get()
            if v in comp_labels:
                s = componentes[comp_labels.index(v)]
                stk = s.get("stock_actual", 0) or 0
                tipo = s.get("tipo", "—")
                self._lbl_stock.config(
                    text=f"  Tipo: {tipo}   Stock actual: {stk} u"
                )

        self._cb_comp.bind("<<ComboboxSelected>>", _on_comp_sel)
        _on_comp_sel()  # cargar al abrir

        self.vCantidad = _entry_row(f, "Cantidad por unidad :", self._data.get("cantidad", 1), 3)
        self.vNivel    = _entry_row(f, "Nivel BOM :",            self._data.get("nivel", 1),    4)
        self.vUnidad   = _entry_row(f, "Unidad de medida :",     self._data.get("unidad", "unidad"), 5)

        # Guardar para _get_values
        self._prod_labels = prod_labels
        self._prod_ids    = prod_ids
        self._comp_labels = comp_labels
        self._comp_ids    = comp_ids

    def _get_values(self):
        if not self._comp_ids:
            raise ValueError("No hay SKUs registrados.")

        def idx_of(var, labels, ids):
            v = var.get()
            return ids[labels.index(v)] if v in labels else None

        prod_id = idx_of(self.vProd, self._prod_labels, self._prod_ids)
        comp_id = idx_of(self.vComp, self._comp_labels, self._comp_ids)
        if prod_id == comp_id:
            raise ValueError("El producto y el componente no pueden ser el mismo SKU.")
        return {
            "producto_id":   prod_id,
            "componente_id": comp_id,
            "cantidad":      _flt(self.vCantidad, "Cantidad", 0.001),
            "nivel":         _int(self.vNivel,    "Nivel",    1),
            "unidad":        self.vUnidad.get().strip() or "unidad",
        }



class _TabBOM(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        ttk.Label(ctrl, text="Producto :", style="In.TLabel").pack(side="left", padx=(4, 2))
        self._skus_all = db.get_skus()
        self._prod_labels = ["(todos)"] + [f"{s['codigo']} — {s['descripcion']}"
                                            for s in self._skus_all]
        self._prod_ids    = [None] + [s["id"] for s in self._skus_all]
        self.vProd = tk.StringVar(value="(todos)")
        self._cb   = ttk.Combobox(ctrl, textvariable=self.vProd,
                                   values=self._prod_labels, state="readonly", width=26)
        self._cb.pack(side="left", padx=2)

        b_ref2 = ttk.Button(ctrl, text="🔄 Actualizar", command=self.refresh)
        b_ref2.pack(side="left", padx=6)
        tip(b_ref2, "Recargar la lista de materiales desde la base de datos.")
        b_add2 = ttk.Button(ctrl, text="➕ Añadir", style="Acc.TButton", command=self._add)
        b_add2.pack(side="left", padx=2)
        tip(b_add2, "Añadir un componente al BOM: selecciona producto terminado, componente, cantidad y nivel.")
        b_edit2 = ttk.Button(ctrl, text="✏ Editar", command=self._edit)
        b_edit2.pack(side="left", padx=2)
        tip(b_edit2, "Editar la relación BOM seleccionada (cantidad, nivel, unidad).")
        b_del2 = ttk.Button(ctrl, text="🗑 Eliminar", command=self._delete)
        b_del2.pack(side="left", padx=2)
        tip(b_del2, "Eliminar la línea BOM seleccionada.")
        b_expl = ttk.Button(ctrl, text="💥 Explotar BOM", command=self._explotar)
        b_expl.pack(side="left", padx=6)
        tip(b_expl, "Calcular los materiales totales necesarios para fabricar una cantidad del producto (MRP multinivel).")

        COLS = ("ID", "Producto", "Nivel", "Componente", "Desc. Componente",
                "Cantidad", "Unidad")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))
        self.rowconfigure(1, weight=1)
        self._tv.column("ID",       width=40)
        self._tv.column("Producto", width=100)
        self._tv.column("Nivel",    width=55)
        self._tv.column("Componente", width=100)
        self._tv.column("Desc. Componente", width=180)
        self._tv.column("Cantidad", width=80)
        self._tv.column("Unidad",   width=70)

        self.refresh()

    def refresh(self):
        self._skus_all = db.get_skus()
        self._prod_labels = ["(todos)"] + [f"{s['codigo']} — {s['descripcion']}"
                                            for s in self._skus_all]
        self._prod_ids    = [None] + [s["id"] for s in self._skus_all]
        self._cb["values"] = self._prod_labels

        prod_id = None
        if self.vProd.get() in self._prod_labels:
            prod_id = self._prod_ids[self._prod_labels.index(self.vProd.get())]

        self._tv.delete(*self._tv.get_children())
        rows = db.get_bom(prod_id) if prod_id else db.get_bom_full()
        for r in rows:
            prod_codigo = r.get("prod_codigo", "")
            self._tv.insert("", "end", values=(
                r["id"],
                prod_codigo if prod_codigo else "—",
                r["nivel"],
                r["comp_codigo"], r["comp_desc"],
                r["cantidad"], r["unidad"]
            ))

    def _selected_row(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione una fila."); return None
        v = self._tv.item(sel[0])["values"]
        # Buscar IDs
        prod_id = comp_id = None
        for s in self._skus_all:
            if s["codigo"] == v[1]:
                prod_id = s["id"]
            if s["codigo"] == v[3]:
                comp_id = s["id"]
        return {"id": v[0], "producto_id": prod_id, "componente_id": comp_id,
                "nivel": v[2], "cantidad": v[5], "unidad": v[6]}

    def _add(self):
        dlg = _BOMDialog(self.winfo_toplevel(), self._skus_all)
        res = dlg.wait()
        if res:
            try:
                db.add_bom(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        row = self._selected_row()
        if not row: return
        dlg = _BOMDialog(self.winfo_toplevel(), self._skus_all, row)
        res = dlg.wait()
        if res:
            try:
                db.update_bom(row["id"], res["cantidad"], res["nivel"], res["unidad"])
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        row = self._selected_row()
        if not row: return
        if messagebox.askyesno("Confirmar", "¿Eliminar esta línea del BOM?"):
            db.delete_bom(row["id"])
            self.refresh()

    def _explotar(self):
        """Ventana de explosión de BOM con requerimientos totales."""
        sel = self._tv.selection()
        # Determinar producto desde el combobox o la selección
        prod_id = None
        if self.vProd.get() in self._prod_labels:
            prod_id = self._prod_ids[self._prod_labels.index(self.vProd.get())]
        if prod_id is None and sel:
            row = self._selected_row()
            if row:
                prod_id = row["producto_id"]
        if prod_id is None:
            messagebox.showinfo("Seleccione producto",
                                 "Seleccione un producto en el filtro superior antes de explotar."); return

        dlg = _ExplotarBOMDialog(self.winfo_toplevel(), prod_id, self._skus_all)
        dlg.grab_set()


class _ExplotarBOMDialog(tk.Toplevel):
    def __init__(self, parent, prod_id, skus_all):
        super().__init__(parent)
        sku = next((s for s in skus_all if s["id"] == prod_id), None)
        self.title(f"Explosión BOM — {sku['codigo'] if sku else prod_id}")
        self.geometry("680x480")
        self.configure(bg=C["bg"])
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._prod_id = prod_id
        self._build()
        self.transient(parent)

    def _build(self):
        ctrl = ttk.Frame(self)
        ctrl.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        ttk.Label(ctrl, text="Cantidad a producir :", style="In.TLabel").pack(side="left", padx=(4, 2))
        self.vQty = tk.StringVar(value="1")
        ttk.Entry(ctrl, textvariable=self.vQty, width=8).pack(side="left", padx=2)
        ttk.Button(ctrl, text="💥 Explotar", style="Acc.TButton",
                   command=self._run).pack(side="left", padx=6)
        ttk.Button(ctrl, text="💾 Exportar CSV",
                   command=self._exportar).pack(side="left", padx=2)

        COLS = ("Nivel", "Código", "Descripción", "Cantidad Req.", "Unidad")
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.rowconfigure(1, weight=1)
        self._run()

    def _run(self):
        try:
            qty = float(self.vQty.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Error", "Cantidad inválida."); return
        items = db.explotar_bom(self._prod_id, qty)
        self._tv.delete(*self._tv.get_children())
        for it in items:
            self._tv.insert("", "end", values=(
                it["nivel"], it["codigo"], it["descripcion"],
                round(it["cantidad_total"], 4), it["unidad"]
            ))
        self._last_items = items

    def _exportar(self):
        if not hasattr(self, "_last_items") or not self._last_items:
            messagebox.showinfo("Sin datos", "Primero explote el BOM."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Exportar BOM Explotado"
        )
        if path:
            pd.DataFrame(self._last_items).to_csv(path, index=False)
            messagebox.showinfo("Exportado", f"BOM exportado en:\n{path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Tab Producción principal
# ═══════════════════════════════════════════════════════════════════════════════

class TabProduccion(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self._tab_mps = _TabMPS(nb)
        self._tab_bom = _TabBOM(nb)

        nb.add(self._tab_mps, text="  📋 MPS  ")
        nb.add(self._tab_bom, text="  🌳 BOM  ")

    def refresh_all(self):
        self._tab_mps.refresh()
        self._tab_bom.refresh()
