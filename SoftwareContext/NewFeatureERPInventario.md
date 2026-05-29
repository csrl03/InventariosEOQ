# NewFeatureERPInventario

**Status**: in-progress  
**Fecha**: 2026-05-27

---

## Resumen

Extensión del Sistema de Inventarios EOQ a un mini-ERP con gestión completa de SKUs, proveedores, clientes, pedidos de compra, MPS/BOM, consumibles con políticas de seguridad, calendario de compras y gráficas de ciclos de demanda. Persistencia con SQLite (sin dependencias externas adicionales).

---

## Decisiones de Arquitectura

| Aspecto | Decisión |
|---|---|
| Persistencia | SQLite local (`inventario.db`) — built-in Python |
| Modelos de lotificación | EOQ + POQ + Lote×Lote + Descuento por cantidad |
| BOM | Multi-nivel (ensambles intermedios) |
| Stock inicial | Manual en GUI + importar CSV |
| Demanda clientes | Anual, externos e internos |

---

## Archivos a Crear

| Archivo | Propósito |
|---|---|
| `database.py` | Capa SQLite: schema, CRUD helpers |
| `gui_utils.py` | Constantes C, F_*, helpers `_entry_row`, `_flt` compartidos |
| `tab_maestro.py` | Tab maestra: SKUs, Proveedores, Clientes, Consumibles |
| `tab_pedidos.py` | Tab pedidos de compra |
| `tab_produccion.py` | Tab producción: MPS + BOM multi-nivel |
| `tab_inventario.py` | Tab inventario: stock, alertas, import CSV |
| `tab_calendario.py` | Tab calendario compras + gráficas ciclos |

## Archivos a Modificar

| Archivo | Cambio |
|---|---|
| `eoq_models.py` | Añadir `POQModel`, `LoteXLote` |
| `app_gui.py` | Importar nuevos tabs, refactorizar constantes a `gui_utils.py`, agregar tabs al Notebook principal |
| `requirements.txt` | Sin cambios (sqlite3 built-in) |

---

## Schema SQLite

```sql
skus            (id, codigo, descripcion, unidad, stock_actual, precio_venta, tipo)
proveedores     (id, nombre, lead_time, contacto, notas)
sku_proveedor   (id, sku_id, proveedor_id, descripcion_proveedor, precio_proveedor, unidad_compra)
clientes        (id, nombre, tipo, demanda_anual, sku_id)
pedidos         (id, fecha_orden, sku_id, proveedor_id, cantidad, unidad, estado, fecha_entrega_esperada, precio_unitario)
consumibles     (id, sku_id, stock_seguridad, politica_seguridad, politica_valor, modelo_lotificacion)
bom             (id, producto_id, componente_id, cantidad, nivel, unidad)
mps             (id, sku_id, periodo, cantidad_planificada, cantidad_real)
```

---

## Nuevas Pestañas en Notebook Principal

```
[ Maestro ]  [ Pedidos ]  [ Producción ]  [ Inventario ]  [ Calendario ]
[ EOQ Clásico ]  [ EOQ Faltantes ]  [ Rev. Periódica ]  [ Inv. Seguridad ]  [ Descuentos ]
```

### Tab Maestro — 4 sub-tabs
- **SKUs**: tabla con CRUD, columnas: Código, Descripción, Unidad, Tipo, Stock, Precio. Botón "Proveedores del SKU" abre diálogo de asociación proveedor↔SKU.
- **Proveedores**: tabla con CRUD, columnas: Nombre, Lead Time (días), Contacto, Notas.
- **Clientes**: tabla con CRUD, columnas: Nombre, Tipo, Demanda Anual, SKU asociado.
- **Consumibles**: tabla con CRUD adicional para política de seguridad y modelo de lotificación.

### Tab Pedidos
- Treeview de todos los pedidos con columnas: #, Fecha, SKU, Proveedor, Cantidad, Unidad, Precio, Estado, Entrega Esperada.
- Botones: Nuevo pedido (fecha auto), Editar, Marcar recibido, Eliminar, Exportar CSV.

### Tab Producción — 2 sub-tabs
- **MPS**: grilla mes×SKU con cantidades planificadas/reales. Botones: cargar, editar celda, exportar.
- **BOM**: árbol jerárquico por producto. CRUD de componentes. Botón "Explotar BOM" para MRP.

### Tab Inventario — 3 sub-tabs
- **Stock actual**: tabla SKU + stock + stock_seguridad + estado (OK / ALERTA).
- **Alertas**: lista filtrada de SKUs bajo política de seguridad.
- **Importar CSV**: FileDialog, mapeo de columnas, vista previa, botón importar.

### Tab Calendario — 2 sub-tabs
- **Calendario de Compras**: pedidos en timeline mensual. Botón generar pedidos desde EOQ.
- **Ciclos de Demanda**: selector de SKU(s), matplotlib mostrando nivel de inventario en el tiempo.

---

## Checklist de Implementación

- [ ] `database.py` — Schema + CRUD helpers
- [ ] `gui_utils.py` — Constantes y helpers compartidos
- [ ] `eoq_models.py` — Añadir POQModel + LoteXLote
- [ ] `tab_maestro.py` — 4 sub-tabs + diálogos CRUD
- [ ] `tab_pedidos.py` — Pedidos + formulario
- [ ] `tab_produccion.py` — MPS + BOM
- [ ] `tab_inventario.py` — Stock + Alertas + CSV
- [ ] `tab_calendario.py` — Calendario + Gráficas
- [ ] `app_gui.py` — Integrar nuevas tabs + actualizar header
