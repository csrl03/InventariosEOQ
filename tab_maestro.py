"""
tab_maestro.py — Pestaña Maestro: Categorías, SKUs, Proveedores, Clientes, Consumibles
========================================================================================
5 sub-pestañas con tablas CRUD completas.
"""

import re
import tkinter as tk
from tkinter import ttk, messagebox

import database as db
from gui_utils import C, F_TITULO, F_LABEL, F_BOLD, F_BOTON, F_SMALL, F_H2
from gui_utils import _entry_row, _flt, make_treeview, crud_toolbar, SimpleDialog, tip


# ─── Diálogos ─────────────────────────────────────────────────────────────────

# ── Colores comunes con código de 2 letras ──
COLORES_PREDEF = [
    "NA", "RO", "AZ", "VE", "AM", "BL", "NE", "GR",
    "PL", "DO", "NA", "MR", "BE", "LI", "TU",
]
COLORES_NOMBRES = {
    "NA": "N/A", "RO": "Rojo", "AZ": "Azul", "VE": "Verde", "AM": "Amarillo",
    "BL": "Blanco", "NE": "Negro", "GR": "Gris", "PL": "Plateado", "DO": "Dorado",
    "MR": "Marrón", "BE": "Beige", "LI": "Lila", "TU": "Turquesa",
}


class _CategoriaDialog(SimpleDialog):
    def __init__(self, parent, data=None):
        self._data = data or {}
        super().__init__(parent, "Categoría — " + ("Editar" if data else "Nueva"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)
        self.vNombre = _entry_row(f, "Nombre :",       self._data.get("nombre", ""),      0)
        self.vCodigo = _entry_row(f, "Código (3 car):", self._data.get("codigo", ""),      1, ancho=6)
        self.vDesc   = _entry_row(f, "Descripción :",  self._data.get("descripcion", ""), 2)
        ttk.Label(f, text="El código se usa en la nomenclatura del SKU (3 caracteres, e.g. FER, ELE, INS)",
                  style="Dim.TLabel").grid(row=3, column=0, columnspan=2,
                                            sticky="w", padx=10, pady=(2, 0))

    def _get_values(self):
        nombre = self.vNombre.get().strip()
        codigo = self.vCodigo.get().strip().upper()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        if not codigo:
            raise ValueError("El código no puede estar vacío.")
        if len(codigo) > 3:
            raise ValueError("El código debe tener máximo 3 caracteres.")
        return {
            "nombre":      nombre,
            "codigo":      codigo,
            "descripcion": self.vDesc.get().strip(),
        }


class _SKUDialog(SimpleDialog):
    TIPOS = ["producto", "consumible", "materia_prima"]

    def __init__(self, parent, data=None):
        self._data = data or {}
        super().__init__(parent, "SKU — " + ("Editar" if data else "Nuevo"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        # ── Sección: código auto-generado ───────────────────────────────────
        ttk.Label(f, text="▸ Nomenclatura automática del SKU",
                  style="Sub.TLabel").grid(row=0, column=0, columnspan=3,
                                            sticky="w", padx=10, pady=(4, 2))

        # Proveedor principal
        ttk.Label(f, text="Proveedor :", style="In.TLabel").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=3)
        self._provs       = db.get_proveedores()
        prov_labels       = ["(ninguno)"] + [p["nombre"] for p in self._provs]
        self._prov_ids    = [None]        + [p["id"]     for p in self._provs]
        self.vProv        = tk.StringVar()
        cur_prov = self._data.get("proveedor_principal_id")
        if cur_prov and cur_prov in self._prov_ids:
            self.vProv.set(prov_labels[self._prov_ids.index(cur_prov)])
        else:
            self.vProv.set(prov_labels[0])
        cb_prov = ttk.Combobox(f, textvariable=self.vProv, values=prov_labels,
                                state="readonly", width=22)
        cb_prov.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=3)
        cb_prov.bind("<<ComboboxSelected>>", self._auto_generar)

        # Código producto (3 chars)
        ttk.Label(f, text="Cód. producto (3) :", style="In.TLabel").grid(
            row=2, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vCodProd = tk.StringVar(value=self._data.get("cod_producto", ""))
        e_cp = ttk.Entry(f, textvariable=self.vCodProd, width=5, style="In.TEntry")
        e_cp.grid(row=2, column=1, sticky="w", padx=(0, 4), pady=3)
        e_cp.bind("<KeyRelease>", self._auto_generar)
        ttk.Label(f, text="Ej: TOR, CAB, CLA", style="Dim.TLabel").grid(
            row=2, column=2, sticky="w")

        # Categoría (código 3 chars)
        ttk.Label(f, text="Categoría :", style="In.TLabel").grid(
            row=3, column=0, sticky="w", padx=(10, 4), pady=3)
        self._cats       = db.get_categorias()
        cat_labels       = ["(ninguna)"] + [f"{c['codigo']} — {c['nombre']}" for c in self._cats]
        self._cat_ids    = [None]        + [c["id"] for c in self._cats]
        self._cat_codigos = [None]       + [c["codigo"] for c in self._cats]
        self.vCat        = tk.StringVar()
        cur_cat = self._data.get("categoria_id")
        if cur_cat and cur_cat in self._cat_ids:
            self.vCat.set(cat_labels[self._cat_ids.index(cur_cat)])
        else:
            self.vCat.set(cat_labels[0])
        cb_cat = ttk.Combobox(f, textvariable=self.vCat, values=cat_labels,
                               state="readonly", width=22)
        cb_cat.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=3)
        cb_cat.bind("<<ComboboxSelected>>", self._auto_generar)

        # Color (2 chars)
        ttk.Label(f, text="Color (2 car.) :", style="In.TLabel").grid(
            row=4, column=0, sticky="w", padx=(10, 4), pady=3)
        color_labels = [f"{k} — {v}" for k, v in COLORES_NOMBRES.items()]
        self.vColor  = tk.StringVar(value=self._data.get("cod_color", "NA"))
        cb_color = ttk.Combobox(f, textvariable=self.vColor, values=color_labels,
                                 width=18)
        cb_color.grid(row=4, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=3)
        cb_color.bind("<<ComboboxSelected>>", self._auto_generar)
        cb_color.bind("<KeyRelease>", self._auto_generar)

        # Código generado (preview + manual override)
        ttk.Label(f, text="Código SKU :", style="In.TLabel").grid(
            row=5, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vCodigo = tk.StringVar(value=self._data.get("codigo", ""))
        ttk.Entry(f, textvariable=self.vCodigo, width=16, style="In.TEntry",
                  font=("Consolas", 10, "bold")).grid(
            row=5, column=1, sticky="w", padx=(0, 4), pady=3)
        ttk.Button(f, text="⚙ Re-generar",
                   command=self._auto_generar).grid(row=5, column=2, sticky="w")
        ttk.Label(f, text="Formato: [PROV][PROD][CAT][COLOR]  (editable)",
                  style="Dim.TLabel").grid(row=6, column=0, columnspan=3,
                                            sticky="w", padx=10, pady=(0, 4))

        ttk.Separator(f, orient="horizontal").grid(
            row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=4)

        # ── Sección: datos del SKU ──────────────────────────────────────────
        ttk.Label(f, text="▸ Datos del producto",
                  style="Sub.TLabel").grid(row=8, column=0, columnspan=3,
                                            sticky="w", padx=10, pady=(0, 2))

        self.vDesc   = _entry_row(f, "Descripción :",     self._data.get("descripcion", ""), 9)
        self.vUnidad = _entry_row(f, "Unidad :",          self._data.get("unidad", "unidad"), 10)
        self.vStock  = _entry_row(f, "Stock actual :",    self._data.get("stock_actual", 0),  11)
        self.vPrecio = _entry_row(f, "Precio de venta :", self._data.get("precio_venta", 0),  12)

        ttk.Label(f, text="Tipo :", style="In.TLabel").grid(
            row=13, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vTipo = tk.StringVar(value=self._data.get("tipo", "producto"))
        ttk.Combobox(f, textvariable=self.vTipo, values=self.TIPOS,
                     state="readonly", width=16).grid(
            row=13, column=1, columnspan=2, sticky="w", padx=(0, 10), pady=3)

        # Auto-generate on first open if new SKU
        if not self._data:
            self._auto_generar()

    def _auto_generar(self, _=None):
        """Genera el código SKU desde los componentes seleccionados."""
        # Proveedor
        prov_label = self.vProv.get()
        prov_nombre = ""
        if prov_label != "(ninguno)" and prov_label in [p["nombre"] for p in self._provs]:
            prov_nombre = prov_label

        # Código producto
        cod_prod = self.vCodProd.get().strip()
        if not cod_prod and self.vDesc.get().strip():
            desc     = re.sub(r'[^A-Za-záéíóúüñÁÉÍÓÚÜÑ ]', '', self.vDesc.get())
            cod_prod = desc.strip().replace(" ", "")[:3].upper()

        # Categoría
        cat_label = self.vCat.get()
        cod_cat   = ""
        idx_cat   = None
        if cat_label in [f"{c['codigo']} — {c['nombre']}" for c in self._cats]:
            idx_cat = next(i for i, c in enumerate(self._cats)
                           if f"{c['codigo']} — {c['nombre']}" == cat_label)
            cod_cat = self._cats[idx_cat]["codigo"]

        # Color
        color_raw = self.vColor.get().split("—")[0].strip()[:2].upper()
        cod_color = color_raw if color_raw else "NA"

        if prov_nombre or cod_prod or cod_cat:
            codigo = db.generar_codigo_sku(prov_nombre or "XX", cod_prod, cod_cat, cod_color)
            self.vCodigo.set(codigo)

    def _get_values(self):
        codigo = self.vCodigo.get().strip().upper()
        desc   = self.vDesc.get().strip()
        unidad = self.vUnidad.get().strip()
        if not codigo:
            raise ValueError("El código SKU no puede estar vacío.")
        if not desc:
            raise ValueError("La descripción no puede estar vacía.")
        if not unidad:
            raise ValueError("La unidad no puede estar vacía.")

        # Resolve IDs
        prov_label = self.vProv.get()
        prov_id    = None
        if prov_label != "(ninguno)":
            for p in self._provs:
                if p["nombre"] == prov_label:
                    prov_id = p["id"]; break

        cat_label = self.vCat.get()
        cat_id    = None
        for i, c in enumerate(self._cats):
            if f"{c['codigo']} — {c['nombre']}" == cat_label:
                cat_id = c["id"]; break

        color_raw  = self.vColor.get().split("—")[0].strip()[:2].upper()
        cod_color  = color_raw if color_raw else "NA"
        cod_prod   = (self.vCodProd.get().strip().upper() + "XXX")[:3]

        return {
            "codigo":                  codigo,
            "descripcion":             desc,
            "unidad":                  unidad,
            "stock_actual":            _flt(self.vStock,  "Stock",  0),
            "precio_venta":            _flt(self.vPrecio, "Precio", 0),
            "tipo":                    self.vTipo.get(),
            "categoria_id":            cat_id,
            "cod_producto":            cod_prod,
            "cod_color":               cod_color,
            "proveedor_principal_id":  prov_id,
        }


class _ProveedorDialog(SimpleDialog):
    def __init__(self, parent, data=None):
        self._data = data or {}
        super().__init__(parent, "Proveedor — " + ("Editar" if data else "Nuevo"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        self.vNombre   = _entry_row(f, "Nombre :",         self._data.get("nombre", ""),    0)
        self.vLeadTime = _entry_row(f, "Lead Time (días):", self._data.get("lead_time", 0), 1)
        self.vContacto = _entry_row(f, "Contacto :",       self._data.get("contacto", ""),  2)
        self.vNotas    = _entry_row(f, "Notas :",          self._data.get("notas", ""),     3)

    def _get_values(self):
        nombre = self.vNombre.get().strip()
        if not nombre:
            raise ValueError("El nombre del proveedor no puede estar vacío.")
        return {
            "nombre":    nombre,
            "lead_time": int(_flt(self.vLeadTime, "Lead Time", 0)),
            "contacto":  self.vContacto.get().strip(),
            "notas":     self.vNotas.get().strip(),
        }


class _ClienteDialog(SimpleDialog):
    TIPOS = ["externo", "interno"]

    def __init__(self, parent, skus, data=None):
        self._data = data or {}
        self._skus = skus          # [(id, codigo, descripcion), ...]
        super().__init__(parent, "Cliente — " + ("Editar" if data else "Nuevo"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        self.vNombre  = _entry_row(f, "Nombre :",        self._data.get("nombre", ""),      0)
        self.vDemanda = _entry_row(f, "Demanda anual :", self._data.get("demanda_anual", 0), 1)

        ttk.Label(f, text="Tipo :", style="In.TLabel").grid(
            row=2, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vTipo = tk.StringVar(value=self._data.get("tipo", "externo"))
        ttk.Combobox(f, textvariable=self.vTipo, values=self.TIPOS,
                     state="readonly", width=12).grid(
            row=2, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(f, text="SKU asociado :", style="In.TLabel").grid(
            row=3, column=0, sticky="w", padx=(10, 4), pady=3)
        self._sku_labels = ["(ninguno)"] + [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [None] + [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar()
        cur_id = self._data.get("sku_id")
        if cur_id and cur_id in self._sku_ids:
            self.vSKU.set(self._sku_labels[self._sku_ids.index(cur_id)])
        else:
            self.vSKU.set(self._sku_labels[0])
        ttk.Combobox(f, textvariable=self.vSKU, values=self._sku_labels,
                     state="readonly", width=24).grid(
            row=3, column=1, sticky="ew", padx=(0, 10), pady=3)

    def _get_values(self):
        nombre = self.vNombre.get().strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        idx    = self._sku_labels.index(self.vSKU.get()) if self.vSKU.get() in self._sku_labels else 0
        sku_id = self._sku_ids[idx]
        return {
            "nombre":        nombre,
            "tipo":          self.vTipo.get(),
            "demanda_anual": _flt(self.vDemanda, "Demanda", 0),
            "sku_id":        sku_id,
        }


class _ConsumibleDialog(SimpleDialog):
    POLITICAS = ["ss_fijo", "z_score", "dias_cobertura"]
    MODELOS   = ["eoq", "poq", "lxl", "cantidad_fija"]

    def __init__(self, parent, skus, data=None):
        self._data = data or {}
        self._skus = skus
        super().__init__(parent, "Consumible — " + ("Editar" if data else "Nuevo"))

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="SKU :", style="In.TLabel").grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=3)
        self._sku_labels = [f"{s['codigo']} — {s['descripcion']}" for s in self._skus]
        self._sku_ids    = [s["id"] for s in self._skus]
        self.vSKU = tk.StringVar()
        cur_id = self._data.get("sku_id")
        if cur_id and cur_id in self._sku_ids:
            self.vSKU.set(self._sku_labels[self._sku_ids.index(cur_id)])
        elif self._sku_labels:
            self.vSKU.set(self._sku_labels[0])
        cb_sku = ttk.Combobox(f, textvariable=self.vSKU, values=self._sku_labels,
                               state="readonly", width=26)
        cb_sku.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=3)

        self.vSS     = _entry_row(f, "Stock seguridad :", self._data.get("stock_seguridad", 0),  1)
        self.vPVal   = _entry_row(f, "Valor política :", self._data.get("politica_valor", 0),    2)

        ttk.Label(f, text="Política SS :", style="In.TLabel").grid(
            row=3, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vPol = tk.StringVar(value=self._data.get("politica_seguridad", "ss_fijo"))
        ttk.Combobox(f, textvariable=self.vPol, values=self.POLITICAS,
                     state="readonly", width=18).grid(
            row=3, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(f, text="Modelo lotificación :", style="In.TLabel").grid(
            row=4, column=0, sticky="w", padx=(10, 4), pady=3)
        self.vMod = tk.StringVar(value=self._data.get("modelo_lotificacion", "eoq"))
        ttk.Combobox(f, textvariable=self.vMod, values=self.MODELOS,
                     state="readonly", width=14).grid(
            row=4, column=1, sticky="ew", padx=(0, 10), pady=3)

        ttk.Label(f, text=(
            "Política ss_fijo → valor = unidades fijas\n"
            "z_score → valor = factor z  |  dias_cobertura → días"
        ), style="Dim.TLabel").grid(row=5, column=0, columnspan=2,
                                     sticky="w", padx=10, pady=(2, 0))

    def _get_values(self):
        if not self._sku_ids:
            raise ValueError("No hay SKUs disponibles. Cree primero un SKU.")
        idx = self._sku_labels.index(self.vSKU.get()) if self.vSKU.get() in self._sku_labels else 0
        return {
            "sku_id":              self._sku_ids[idx],
            "stock_seguridad":     _flt(self.vSS,   "Stock seguridad", 0),
            "politica_seguridad":  self.vPol.get(),
            "politica_valor":      _flt(self.vPVal, "Valor política",  0),
            "modelo_lotificacion": self.vMod.get(),
        }


class _SKUProveedorDialog(SimpleDialog):
    """Diálogo para asociar un proveedor a un SKU (precio, unidad, descripción)."""

    def __init__(self, parent, proveedores, data=None):
        self._data  = data or {}
        self._provs = proveedores
        super().__init__(parent, "Asociar Proveedor al SKU")

    def _build_form(self):
        f = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Proveedor :", style="In.TLabel").grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=3)
        self._prov_labels = [p["nombre"] for p in self._provs]
        self._prov_ids    = [p["id"]     for p in self._provs]
        self.vProv = tk.StringVar()
        cur_id = self._data.get("proveedor_id")
        if cur_id and cur_id in self._prov_ids:
            self.vProv.set(self._prov_labels[self._prov_ids.index(cur_id)])
        elif self._prov_labels:
            self.vProv.set(self._prov_labels[0])
        ttk.Combobox(f, textvariable=self.vProv, values=self._prov_labels,
                     state="readonly", width=22).grid(
            row=0, column=1, sticky="ew", padx=(0, 10), pady=3)

        self.vDescProv = _entry_row(f, "Desc. proveedor :", self._data.get("descripcion_proveedor", ""), 1)
        self.vPrecio   = _entry_row(f, "Precio proveedor :", self._data.get("precio_proveedor", 0),      2)
        self.vUnidad   = _entry_row(f, "Unidad de compra :", self._data.get("unidad_compra", "unidad"),  3)

    def _get_values(self):
        if not self._prov_ids:
            raise ValueError("No hay proveedores. Cree primero un proveedor.")
        idx = self._prov_labels.index(self.vProv.get()) if self.vProv.get() in self._prov_labels else 0
        return {
            "proveedor_id":           self._prov_ids[idx],
            "descripcion_proveedor":  self.vDescProv.get().strip(),
            "precio_proveedor":       _flt(self.vPrecio, "Precio", 0),
            "unidad_compra":          self.vUnidad.get().strip() or "unidad",
        }


# ─── Sub-pestaña SKUs ─────────────────────────────────────────────────────────

class _TabSKUs(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        self._all_skus = []
        self._build()

    def _build(self):
        COLS = ("ID", "Código", "Descripción", "Categoría", "Color",
                "Tipo", "Proveedor", "Unidad", "Stock", "Precio Venta")
        toolbar = crud_toolbar(
            self,
            on_add=self._add,
            on_edit=self._edit,
            on_delete=self._delete,
            extras=[("🔗  Proveedores del SKU", self._ver_proveedores)],
            tip_add="Crear un nuevo SKU (producto, materia prima o consumible) en el catálogo.",
            tip_edit="Editar los datos del SKU seleccionado.",
            tip_del="Eliminar el SKU del catálogo. No elimina stock ni historial.",
            tips_extras=["Ver y gestionar los proveedores asociados a este SKU, con precio y lead time."],
        )
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        # ── Barra de filtros ──────────────────────────────────────────────
        flt = ttk.Frame(self)
        flt.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))

        ttk.Label(flt, text="🔍 Buscar :", style="In.TLabel").pack(side="left", padx=(2, 2))
        self.vBuscar = tk.StringVar()
        self.vBuscar.trace_add("write", lambda *_: self._aplicar_filtros())
        ttk.Entry(flt, textvariable=self.vBuscar, width=16, style="In.TEntry").pack(
            side="left", padx=2)

        ttk.Label(flt, text="Categoría :", style="In.TLabel").pack(side="left", padx=(8, 2))
        self.vFiltCat = tk.StringVar(value="Todas")
        self._cb_cat  = ttk.Combobox(flt, textvariable=self.vFiltCat,
                                      state="readonly", width=14)
        self._cb_cat.pack(side="left", padx=2)
        self._cb_cat.bind("<<ComboboxSelected>>", lambda _: self._aplicar_filtros())

        ttk.Label(flt, text="Proveedor :", style="In.TLabel").pack(side="left", padx=(8, 2))
        self.vFiltProv = tk.StringVar(value="Todos")
        self._cb_prov  = ttk.Combobox(flt, textvariable=self.vFiltProv,
                                       state="readonly", width=16)
        self._cb_prov.pack(side="left", padx=2)
        self._cb_prov.bind("<<ComboboxSelected>>", lambda _: self._aplicar_filtros())

        ttk.Label(flt, text="Color :", style="In.TLabel").pack(side="left", padx=(8, 2))
        self.vFiltColor = tk.StringVar(value="Todos")
        self._cb_color  = ttk.Combobox(flt, textvariable=self.vFiltColor,
                                        state="readonly", width=10)
        self._cb_color.pack(side="left", padx=2)
        self._cb_color.bind("<<ComboboxSelected>>", lambda _: self._aplicar_filtros())

        ttk.Button(flt, text="✕ Limpiar",
                   command=self._limpiar_filtros).pack(side="left", padx=6)

        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("ID",          width=40,  minwidth=30)
        self._tv.column("Código",      width=100)
        self._tv.column("Descripción", width=170)
        self._tv.column("Categoría",   width=90)
        self._tv.column("Color",       width=60)
        self._tv.column("Tipo",        width=90)
        self._tv.column("Proveedor",   width=120)
        self._tv.column("Unidad",      width=65)
        self._tv.column("Stock",       width=70)
        self._tv.column("Precio Venta", width=85)

        self.refresh()

    def refresh(self):
        self._all_skus = db.get_skus()
        # Actualizar opciones de filtros
        cats  = sorted({s.get("categoria_nombre") or "" for s in self._all_skus if s.get("categoria_nombre")})
        provs = sorted({s.get("proveedor_principal_nombre") or "" for s in self._all_skus if s.get("proveedor_principal_nombre")})
        colrs = sorted({s.get("cod_color") or "" for s in self._all_skus if s.get("cod_color")})
        self._cb_cat["values"]   = ["Todas"]  + cats
        self._cb_prov["values"]  = ["Todos"]  + provs
        self._cb_color["values"] = ["Todos"]  + colrs
        self._aplicar_filtros()

    def _aplicar_filtros(self):
        buscar   = self.vBuscar.get().strip().lower()
        cat_fil  = self.vFiltCat.get()
        prov_fil = self.vFiltProv.get()
        col_fil  = self.vFiltColor.get()

        self._tv.delete(*self._tv.get_children())
        for s in self._all_skus:
            if buscar and buscar not in s["codigo"].lower() and buscar not in s["descripcion"].lower():
                continue
            if cat_fil  != "Todas" and (s.get("categoria_nombre") or "") != cat_fil:
                continue
            if prov_fil != "Todos" and (s.get("proveedor_principal_nombre") or "") != prov_fil:
                continue
            if col_fil  != "Todos" and (s.get("cod_color") or "") != col_fil:
                continue
            self._tv.insert("", "end", values=(
                s["id"], s["codigo"], s["descripcion"],
                s.get("categoria_nombre") or "",
                s.get("cod_color") or "",
                s["tipo"],
                s.get("proveedor_principal_nombre") or "",
                s["unidad"], s["stock_actual"], s["precio_venta"]
            ))

    def _limpiar_filtros(self):
        self.vBuscar.set("")
        self.vFiltCat.set("Todas")
        self.vFiltProv.set("Todos")
        self.vFiltColor.set("Todos")
        self._aplicar_filtros()

    def _selected_id(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un SKU primero."); return None
        return self._tv.item(sel[0])["values"][0]

    def _selected_data(self):
        sel = self._tv.selection()
        if not sel: return None
        sku_id = self._tv.item(sel[0])["values"][0]
        return db.get_sku(sku_id)

    def _add(self):
        dlg = _SKUDialog(self.winfo_toplevel())
        res = dlg.wait()
        if res:
            try:
                db.add_sku(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        data = self._selected_data()
        if not data: return
        dlg = _SKUDialog(self.winfo_toplevel(), data)
        res = dlg.wait()
        if res:
            try:
                db.update_sku(data["id"], **res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        sku_id = self._selected_id()
        if sku_id is None: return
        if messagebox.askyesno("Confirmar", "¿Eliminar el SKU seleccionado?\nSe eliminarán datos relacionados."):
            db.delete_sku(sku_id)
            self.refresh()

    def _ver_proveedores(self):
        sku_id = self._selected_id()
        if sku_id is None: return
        sku = db.get_sku(sku_id)
        _ProveedoresSKUWindow(self.winfo_toplevel(), sku)


class _ProveedoresSKUWindow(tk.Toplevel):
    """Ventana para gestionar los proveedores asociados a un SKU."""

    def __init__(self, parent, sku):
        super().__init__(parent)
        self.title(f"Proveedores del SKU: {sku['codigo']} — {sku['descripcion']}")
        self.geometry("620x400")
        self.configure(bg=C["bg"])
        self._sku_id = sku["id"]
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        COLS = ("ID", "Proveedor", "Lead Time", "Desc. Proveedor", "Precio", "Unidad Compra")
        toolbar = crud_toolbar(
            self,
            on_add=self._add,
            on_edit=self._edit,
            on_delete=self._delete,
            tip_add="Asociar un proveedor a este SKU con su precio y tiempo de entrega.",
            tip_edit="Editar el proveedor o condiciones de compra seleccionados.",
            tip_del="Eliminar la relación SKU-Proveedor seleccionada.",
        )
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        frm_tv, self._tv = make_treeview(self, COLS, height=10)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("ID", width=40)
        self._tv.column("Proveedor", width=140)
        self._tv.column("Lead Time", width=80)
        self.refresh()
        self.transient(parent); self.grab_set()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_sku_proveedores(self._sku_id):
            self._tv.insert("", "end", values=(
                r["id"], r["nombre_proveedor"], r["lead_time"],
                r["descripcion_proveedor"], r["precio_proveedor"], r["unidad_compra"]
            ))

    def _selected_row(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione una fila."); return None
        v = self._tv.item(sel[0])["values"]
        return {"id": v[0], "proveedor_id": None,  # buscamos por nombre
                "descripcion_proveedor": v[3], "precio_proveedor": v[4],
                "unidad_compra": v[5]}

    def _add(self):
        provs = db.get_proveedores()
        if not provs:
            messagebox.showinfo("Sin proveedores", "Primero cree proveedores en la pestaña Proveedores."); return
        dlg = _SKUProveedorDialog(self, provs)
        res = dlg.wait()
        if res:
            try:
                db.upsert_sku_proveedor(self._sku_id, **res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione una fila."); return
        v    = self._tv.item(sel[0])["values"]
        provs = db.get_proveedores()
        data  = {"proveedor_id": None, "descripcion_proveedor": v[3],
                 "precio_proveedor": v[4], "unidad_compra": v[5]}
        # Buscar proveedor_id por nombre
        for p in provs:
            if p["nombre"] == v[1]:
                data["proveedor_id"] = p["id"]; break
        dlg = _SKUProveedorDialog(self, provs, data)
        res = dlg.wait()
        if res:
            try:
                db.upsert_sku_proveedor(self._sku_id, **res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione una fila."); return
        sp_id = self._tv.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirmar", "¿Eliminar esta asociación proveedor-SKU?"):
            db.delete_sku_proveedor(sp_id)
            self.refresh()


# ─── Sub-pestaña Proveedores ──────────────────────────────────────────────────

class _TabProveedores(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        COLS = ("ID", "Nombre", "Lead Time (días)", "Contacto", "Notas")
        toolbar = crud_toolbar(self, on_add=self._add, on_edit=self._edit, on_delete=self._delete,
                                tip_add="Registrar un nuevo proveedor con razón social y datos de contacto.",
                                tip_edit="Editar los datos del proveedor seleccionado.",
                                tip_del="Eliminar el proveedor del catálogo.")
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("ID", width=40)
        self._tv.column("Nombre", width=180)
        self._tv.column("Lead Time (días)", width=110)
        self._tv.column("Contacto", width=150)
        self._tv.column("Notas", width=200)
        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_proveedores():
            self._tv.insert("", "end", values=(
                r["id"], r["nombre"], r["lead_time"], r["contacto"], r["notas"]
            ))

    def _selected_data(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un proveedor."); return None
        v = self._tv.item(sel[0])["values"]
        return {"id": v[0], "nombre": v[1], "lead_time": v[2],
                "contacto": v[3], "notas": v[4]}

    def _add(self):
        dlg = _ProveedorDialog(self.winfo_toplevel())
        res = dlg.wait()
        if res:
            try:
                db.add_proveedor(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        data = self._selected_data()
        if not data: return
        dlg = _ProveedorDialog(self.winfo_toplevel(), data)
        res = dlg.wait()
        if res:
            try:
                db.update_proveedor(data["id"], **res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        data = self._selected_data()
        if not data: return
        if messagebox.askyesno("Confirmar", f"¿Eliminar proveedor '{data['nombre']}'?"):
            db.delete_proveedor(data["id"])
            self.refresh()


# ─── Sub-pestaña Clientes ─────────────────────────────────────────────────────

class _TabClientes(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        COLS = ("ID", "Nombre", "Tipo", "Demanda Anual", "SKU Asociado")
        toolbar = crud_toolbar(self, on_add=self._add, on_edit=self._edit, on_delete=self._delete,
                                tip_add="Registrar un cliente con su demanda anual y SKU de referencia.",
                                tip_edit="Editar los datos del cliente seleccionado.",
                                tip_del="Eliminar el cliente del catálogo.")
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("ID", width=40)
        self._tv.column("Nombre", width=180)
        self._tv.column("Tipo", width=80)
        self._tv.column("Demanda Anual", width=110)
        self._tv.column("SKU Asociado", width=120)
        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_clientes():
            self._tv.insert("", "end", values=(
                r["id"], r["nombre"], r["tipo"],
                r["demanda_anual"], r["sku_codigo"] or ""
            ))

    def _selected_data(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un cliente."); return None
        v = self._tv.item(sel[0])["values"]
        # Buscar sku_id por codigo
        sku_id = None
        if v[4]:
            for s in db.get_skus():
                if s["codigo"] == v[4]:
                    sku_id = s["id"]; break
        return {"id": v[0], "nombre": v[1], "tipo": v[2],
                "demanda_anual": v[3], "sku_id": sku_id}

    def _add(self):
        skus = db.get_skus()
        dlg  = _ClienteDialog(self.winfo_toplevel(), skus)
        res  = dlg.wait()
        if res:
            try:
                db.add_cliente(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        data = self._selected_data()
        if not data: return
        skus = db.get_skus()
        dlg  = _ClienteDialog(self.winfo_toplevel(), skus, data)
        res  = dlg.wait()
        if res:
            try:
                db.update_cliente(data["id"], **res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        data = self._selected_data()
        if not data: return
        if messagebox.askyesno("Confirmar", f"¿Eliminar cliente '{data['nombre']}'?"):
            db.delete_cliente(data["id"])
            self.refresh()


# ─── Sub-pestaña Consumibles ──────────────────────────────────────────────────

class _TabConsumibles(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        COLS = ("SKU Código", "Descripción", "Unidad", "Stock Actual",
                "Stock Seguridad", "Política SS", "Valor Política", "Modelo Lotif.")
        toolbar = crud_toolbar(self, on_add=self._add, on_edit=self._edit, on_delete=self._delete,
                                tip_add="Definir parámetros de reposición para un SKU consumible.",
                                tip_edit="Editar política de inventario de seguridad del consumible seleccionado.",
                                tip_del="Eliminar configuración de consumible.")
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("SKU Código", width=90)
        self._tv.column("Descripción", width=180)
        self._tv.column("Unidad", width=70)
        self._tv.column("Stock Actual", width=90)
        self._tv.column("Stock Seguridad", width=100)
        self._tv.column("Política SS", width=100)
        self._tv.column("Valor Política", width=90)
        self._tv.column("Modelo Lotif.", width=100)
        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_consumibles():
            self._tv.insert("", "end", values=(
                r["codigo"], r["descripcion"], r["unidad"],
                r["stock_actual"], r["stock_seguridad"],
                r["politica_seguridad"], r["politica_valor"],
                r["modelo_lotificacion"]
            ))

    def _selected_sku_id(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un consumible."); return None
        codigo = self._tv.item(sel[0])["values"][0]
        for s in db.get_skus():
            if s["codigo"] == codigo:
                return s["id"]
        return None

    def _add(self):
        skus = db.get_skus()
        dlg  = _ConsumibleDialog(self.winfo_toplevel(), skus)
        res  = dlg.wait()
        if res:
            try:
                db.upsert_consumible(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione un consumible."); return
        codigo = self._tv.item(sel[0])["values"][0]
        sku_id = None
        for s in db.get_skus():
            if s["codigo"] == codigo:
                sku_id = s["id"]; break
        if sku_id is None: return
        data = db.get_consumible_by_sku(sku_id) or {}
        skus = db.get_skus()
        dlg  = _ConsumibleDialog(self.winfo_toplevel(), skus, data)
        res  = dlg.wait()
        if res:
            try:
                db.upsert_consumible(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        sku_id = self._selected_sku_id()
        if sku_id is None: return
        if messagebox.askyesno("Confirmar", "¿Eliminar registro de consumible?"):
            db.delete_consumible(sku_id)
            self.refresh()


# ─── Sub-pestaña Categorías ───────────────────────────────────────────────────

class _TabCategorias(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        COLS = ("ID", "Código", "Nombre", "Descripción")
        toolbar = crud_toolbar(self, on_add=self._add, on_edit=self._edit, on_delete=self._delete,
                                tip_add="Crear una nueva categoría para clasificar SKUs.",
                                tip_edit="Editar el nombre o descripción de la categoría seleccionada.",
                                tip_del="Eliminar la categoría (los SKUs asociados quedan sin categoría).")
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        frm_tv, self._tv = make_treeview(self, COLS)
        frm_tv.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tv.column("ID",           width=40)
        self._tv.column("Código",       width=70)
        self._tv.column("Nombre",       width=180)
        self._tv.column("Descripción",  width=280)
        self.refresh()

    def refresh(self):
        self._tv.delete(*self._tv.get_children())
        for r in db.get_categorias():
            self._tv.insert("", "end", values=(
                r["id"], r["codigo"], r["nombre"], r["descripcion"]
            ))

    def _selected_data(self):
        sel = self._tv.selection()
        if not sel:
            messagebox.showwarning("Selección", "Seleccione una categoría."); return None
        v = self._tv.item(sel[0])["values"]
        return {"id": v[0], "codigo": v[1], "nombre": v[2], "descripcion": v[3]}

    def _add(self):
        dlg = _CategoriaDialog(self.winfo_toplevel())
        res = dlg.wait()
        if res:
            try:
                db.add_categoria(**res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _edit(self):
        data = self._selected_data()
        if not data: return
        dlg = _CategoriaDialog(self.winfo_toplevel(), data)
        res = dlg.wait()
        if res:
            try:
                db.update_categoria(data["id"], **res)
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete(self):
        data = self._selected_data()
        if not data: return
        if messagebox.askyesno("Confirmar",
                               f"¿Eliminar categoría '{data['nombre']}'?\n"
                               "Los SKUs asociados quedarán sin categoría."):
            db.delete_categoria(data["id"])
            self.refresh()


# ─── Tab Maestro principal ────────────────────────────────────────────────────

class TabMaestro(ttk.Frame):
    """
    Pestaña principal con sub-tabs: Categorías | SKUs | Proveedores | Clientes | Consumibles.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self._tab_categorias  = _TabCategorias(nb)
        self._tab_skus        = _TabSKUs(nb)
        self._tab_proveedores = _TabProveedores(nb)
        self._tab_clientes    = _TabClientes(nb)
        self._tab_consumibles = _TabConsumibles(nb)

        nb.add(self._tab_categorias,  text="  🏷 Categorías  ")
        nb.add(self._tab_skus,        text="  📦 SKUs  ")
        nb.add(self._tab_proveedores, text="  🏭 Proveedores  ")
        nb.add(self._tab_clientes,    text="  👥 Clientes  ")
        nb.add(self._tab_consumibles, text="  🧪 Consumibles  ")

    def refresh_all(self):
        self._tab_categorias.refresh()
        self._tab_skus.refresh()
        self._tab_proveedores.refresh()
        self._tab_clientes.refresh()
        self._tab_consumibles.refresh()
