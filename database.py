"""
database.py — Capa de persistencia SQLite
==========================================
Schema + helpers CRUD para el Sistema ERP-Inventario.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "inventario.db"


# ─── Conexión ─────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─── Inicialización del schema ────────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS categorias (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT UNIQUE NOT NULL,
            codigo      TEXT UNIQUE NOT NULL,
            descripcion TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS skus (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo                  TEXT    UNIQUE NOT NULL,
            descripcion             TEXT    NOT NULL,
            unidad                  TEXT    NOT NULL DEFAULT 'unidad',
            stock_actual            REAL    DEFAULT 0,
            precio_venta            REAL    DEFAULT 0,
            tipo                    TEXT    DEFAULT 'producto',
            categoria_id            INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
            cod_producto            TEXT    DEFAULT '',
            cod_color               TEXT    DEFAULT 'NA',
            proveedor_principal_id  INTEGER REFERENCES proveedores(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS proveedores (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre     TEXT UNIQUE NOT NULL,
            lead_time  INTEGER DEFAULT 0,
            contacto   TEXT    DEFAULT '',
            notas      TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sku_proveedor (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id               INTEGER NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
            proveedor_id         INTEGER NOT NULL REFERENCES proveedores(id) ON DELETE CASCADE,
            descripcion_proveedor TEXT   DEFAULT '',
            precio_proveedor     REAL   DEFAULT 0,
            unidad_compra        TEXT   DEFAULT 'unidad',
            UNIQUE(sku_id, proveedor_id)
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT NOT NULL,
            tipo          TEXT DEFAULT 'externo',
            demanda_anual REAL DEFAULT 0,
            sku_id        INTEGER REFERENCES skus(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_orden            TEXT    NOT NULL,
            sku_id                 INTEGER REFERENCES skus(id) ON DELETE SET NULL,
            proveedor_id           INTEGER REFERENCES proveedores(id) ON DELETE SET NULL,
            cantidad               REAL    NOT NULL DEFAULT 0,
            unidad                 TEXT    DEFAULT 'unidad',
            estado                 TEXT    DEFAULT 'pendiente',
            fecha_entrega_esperada TEXT    DEFAULT '',
            precio_unitario        REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS consumibles (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id              INTEGER UNIQUE REFERENCES skus(id) ON DELETE CASCADE,
            stock_seguridad     REAL    DEFAULT 0,
            politica_seguridad  TEXT    DEFAULT 'ss_fijo',
            politica_valor      REAL    DEFAULT 0,
            modelo_lotificacion TEXT    DEFAULT 'eoq'
        );

        CREATE TABLE IF NOT EXISTS bom (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id   INTEGER NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
            componente_id INTEGER NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
            cantidad      REAL    NOT NULL DEFAULT 1,
            nivel         INTEGER DEFAULT 1,
            unidad        TEXT    DEFAULT 'unidad',
            UNIQUE(producto_id, componente_id)
        );

        CREATE TABLE IF NOT EXISTS mps (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_id              INTEGER NOT NULL REFERENCES skus(id) ON DELETE CASCADE,
            periodo             TEXT    NOT NULL,
            cantidad_planificada REAL   DEFAULT 0,
            cantidad_real       REAL    DEFAULT 0,
            UNIQUE(sku_id, periodo)
        );

        CREATE TABLE IF NOT EXISTS facturas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            numero       TEXT UNIQUE NOT NULL,
            fecha        TEXT NOT NULL,
            proveedor_id INTEGER REFERENCES proveedores(id) ON DELETE SET NULL,
            metodo_pago  TEXT DEFAULT 'efectivo',
            notas        TEXT DEFAULT '',
            total        REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS factura_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id      INTEGER NOT NULL REFERENCES facturas(id) ON DELETE CASCADE,
            sku_id          INTEGER REFERENCES skus(id) ON DELETE SET NULL,
            cantidad        REAL    NOT NULL DEFAULT 0,
            unidad          TEXT    DEFAULT 'unidad',
            precio_unitario REAL    DEFAULT 0,
            subtotal        REAL    DEFAULT 0
        );
        """)
    _run_migrations()


# ─── CRUD genérico ────────────────────────────────────────────────────────────

def fetchall(query: str, params=()):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def fetchone(query: str, params=()):
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def execute(query: str, params=()):
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return cur.lastrowid


# ─── Migraciones (columnas nuevas en tablas existentes) ───────────────────────

def _run_migrations():
    """Agrega columnas a tablas existentes si no existen (idempotente)."""
    migrations = [
        ("skus", "categoria_id",           "INTEGER REFERENCES categorias(id) ON DELETE SET NULL"),
        ("skus", "cod_producto",            "TEXT DEFAULT ''"),
        ("skus", "cod_color",               "TEXT DEFAULT 'NA'"),
        ("skus", "proveedor_principal_id",  "INTEGER REFERENCES proveedores(id) ON DELETE SET NULL"),
    ]
    with get_conn() as conn:
        for tabla, columna, tipo in migrations:
            cols = [row[1] for row in conn.execute(f"PRAGMA table_info({tabla})").fetchall()]
            if columna not in cols:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")


# ─── Generador de código SKU ─────────────────────────────────────────────────

def generar_codigo_sku(prov_nombre: str, cod_producto: str,
                       cod_categoria: str, cod_color: str) -> str:
    """
    Genera código SKU con el formato:
    [INICIALES_PROV(≤3)][COD_PROD(3)][COD_CAT(3)][COD_COLOR(2)]
    Ejemplo: 'Ferretería Norte' + 'TOR' + 'FER' + 'PL' → 'FNTORFERPL'
    """
    palabras   = [p for p in prov_nombre.split() if p]
    iniciales  = "".join(p[0] for p in palabras)[:3].upper()
    cod_prod   = (cod_producto.strip().upper() + "XXX")[:3]
    cod_cat    = (cod_categoria.strip().upper() + "XXX")[:3]
    cod_col    = (cod_color.strip().upper() + "NA")[:2]
    return iniciales + cod_prod + cod_cat + cod_col


# ─── Categorías ───────────────────────────────────────────────────────────────

def get_categorias():
    return fetchall("SELECT * FROM categorias ORDER BY nombre")


def add_categoria(nombre, codigo, descripcion=""):
    return execute(
        "INSERT INTO categorias(nombre,codigo,descripcion) VALUES(?,?,?)",
        (nombre, codigo.upper(), descripcion)
    )


def update_categoria(cat_id, nombre, codigo, descripcion):
    execute(
        "UPDATE categorias SET nombre=?,codigo=?,descripcion=? WHERE id=?",
        (nombre, codigo.upper(), descripcion, cat_id)
    )


def delete_categoria(cat_id):
    execute("DELETE FROM categorias WHERE id=?", (cat_id,))


# ─── SKUs ─────────────────────────────────────────────────────────────────────

def get_skus():
    return fetchall(
        "SELECT s.*, c.nombre AS categoria_nombre, c.codigo AS categoria_codigo, "
        "p.nombre AS proveedor_principal_nombre "
        "FROM skus s "
        "LEFT JOIN categorias c ON c.id=s.categoria_id "
        "LEFT JOIN proveedores p ON p.id=s.proveedor_principal_id "
        "ORDER BY s.codigo"
    )


def get_sku(sku_id):
    return fetchone(
        "SELECT s.*, c.nombre AS categoria_nombre, c.codigo AS categoria_codigo, "
        "p.nombre AS proveedor_principal_nombre "
        "FROM skus s "
        "LEFT JOIN categorias c ON c.id=s.categoria_id "
        "LEFT JOIN proveedores p ON p.id=s.proveedor_principal_id "
        "WHERE s.id=?",
        (sku_id,)
    )


def add_sku(codigo, descripcion, unidad, stock_actual=0, precio_venta=0, tipo="producto",
            categoria_id=None, cod_producto="", cod_color="NA",
            proveedor_principal_id=None):
    return execute(
        "INSERT INTO skus(codigo,descripcion,unidad,stock_actual,precio_venta,tipo,"
        "categoria_id,cod_producto,cod_color,proveedor_principal_id) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (codigo, descripcion, unidad, stock_actual, precio_venta, tipo,
         categoria_id, cod_producto, cod_color, proveedor_principal_id)
    )


def update_sku(sku_id, codigo, descripcion, unidad, stock_actual, precio_venta, tipo,
               categoria_id=None, cod_producto="", cod_color="NA",
               proveedor_principal_id=None):
    execute(
        "UPDATE skus SET codigo=?,descripcion=?,unidad=?,stock_actual=?,"
        "precio_venta=?,tipo=?,categoria_id=?,cod_producto=?,cod_color=?,"
        "proveedor_principal_id=? WHERE id=?",
        (codigo, descripcion, unidad, stock_actual, precio_venta, tipo,
         categoria_id, cod_producto, cod_color, proveedor_principal_id, sku_id)
    )


def delete_sku(sku_id):
    execute("DELETE FROM skus WHERE id=?", (sku_id,))


def update_stock(sku_id, cantidad):
    execute("UPDATE skus SET stock_actual=? WHERE id=?", (cantidad, sku_id))


def add_stock(sku_id, cantidad):
    """Suma cantidad al stock actual."""
    execute("UPDATE skus SET stock_actual=stock_actual+? WHERE id=?", (cantidad, sku_id))


# ─── SKU-Proveedor ────────────────────────────────────────────────────────────

def get_sku_proveedores(sku_id):
    return fetchall(
        "SELECT sp.*, p.nombre AS nombre_proveedor, p.lead_time "
        "FROM sku_proveedor sp JOIN proveedores p ON p.id=sp.proveedor_id "
        "WHERE sp.sku_id=? ORDER BY p.nombre",
        (sku_id,)
    )


def get_skus_por_proveedor(proveedor_id):
    return fetchall(
        "SELECT sp.*, s.codigo, s.descripcion "
        "FROM sku_proveedor sp JOIN skus s ON s.id=sp.sku_id "
        "WHERE sp.proveedor_id=? ORDER BY s.codigo",
        (proveedor_id,)
    )


def upsert_sku_proveedor(sku_id, proveedor_id, descripcion_proveedor, precio_proveedor, unidad_compra):
    execute(
        "INSERT INTO sku_proveedor(sku_id,proveedor_id,descripcion_proveedor,"
        "precio_proveedor,unidad_compra) VALUES(?,?,?,?,?) "
        "ON CONFLICT(sku_id,proveedor_id) DO UPDATE SET "
        "descripcion_proveedor=excluded.descripcion_proveedor,"
        "precio_proveedor=excluded.precio_proveedor,"
        "unidad_compra=excluded.unidad_compra",
        (sku_id, proveedor_id, descripcion_proveedor, precio_proveedor, unidad_compra)
    )


def delete_sku_proveedor(sp_id):
    execute("DELETE FROM sku_proveedor WHERE id=?", (sp_id,))


# ─── Proveedores ──────────────────────────────────────────────────────────────

def get_proveedores():
    return fetchall("SELECT * FROM proveedores ORDER BY nombre")


def add_proveedor(nombre, lead_time=0, contacto="", notas=""):
    return execute(
        "INSERT INTO proveedores(nombre,lead_time,contacto,notas) VALUES(?,?,?,?)",
        (nombre, lead_time, contacto, notas)
    )


def update_proveedor(prov_id, nombre, lead_time, contacto, notas):
    execute(
        "UPDATE proveedores SET nombre=?,lead_time=?,contacto=?,notas=? WHERE id=?",
        (nombre, lead_time, contacto, notas, prov_id)
    )


def delete_proveedor(prov_id):
    execute("DELETE FROM proveedores WHERE id=?", (prov_id,))


# ─── Clientes ─────────────────────────────────────────────────────────────────

def get_clientes():
    return fetchall(
        "SELECT c.*, s.codigo AS sku_codigo FROM clientes c "
        "LEFT JOIN skus s ON s.id=c.sku_id ORDER BY c.nombre"
    )


def add_cliente(nombre, tipo="externo", demanda_anual=0, sku_id=None):
    return execute(
        "INSERT INTO clientes(nombre,tipo,demanda_anual,sku_id) VALUES(?,?,?,?)",
        (nombre, tipo, demanda_anual, sku_id)
    )


def update_cliente(cli_id, nombre, tipo, demanda_anual, sku_id):
    execute(
        "UPDATE clientes SET nombre=?,tipo=?,demanda_anual=?,sku_id=? WHERE id=?",
        (nombre, tipo, demanda_anual, sku_id, cli_id)
    )


def delete_cliente(cli_id):
    execute("DELETE FROM clientes WHERE id=?", (cli_id,))


def get_demanda_total_sku(sku_id):
    """Suma de demanda anual de todos los clientes asociados a un SKU."""
    row = fetchone(
        "SELECT COALESCE(SUM(demanda_anual),0) AS total FROM clientes WHERE sku_id=?",
        (sku_id,)
    )
    return row["total"] if row else 0


# ─── Pedidos ──────────────────────────────────────────────────────────────────

def get_pedidos():
    return fetchall(
        "SELECT p.*, s.codigo AS sku_codigo, s.descripcion AS sku_desc, "
        "pr.nombre AS proveedor_nombre "
        "FROM pedidos p "
        "LEFT JOIN skus s ON s.id=p.sku_id "
        "LEFT JOIN proveedores pr ON pr.id=p.proveedor_id "
        "ORDER BY p.fecha_orden DESC"
    )


def add_pedido(sku_id, proveedor_id, cantidad, unidad, precio_unitario,
               fecha_entrega_esperada="", estado="pendiente"):
    fecha_orden = datetime.now().strftime("%Y-%m-%d")
    return execute(
        "INSERT INTO pedidos(fecha_orden,sku_id,proveedor_id,cantidad,unidad,"
        "estado,fecha_entrega_esperada,precio_unitario) VALUES(?,?,?,?,?,?,?,?)",
        (fecha_orden, sku_id, proveedor_id, cantidad, unidad,
         estado, fecha_entrega_esperada, precio_unitario)
    )


def update_pedido(ped_id, sku_id, proveedor_id, cantidad, unidad, precio_unitario,
                  fecha_entrega_esperada, estado):
    execute(
        "UPDATE pedidos SET sku_id=?,proveedor_id=?,cantidad=?,unidad=?,"
        "precio_unitario=?,fecha_entrega_esperada=?,estado=? WHERE id=?",
        (sku_id, proveedor_id, cantidad, unidad, precio_unitario,
         fecha_entrega_esperada, estado, ped_id)
    )


def delete_pedido(ped_id):
    execute("DELETE FROM pedidos WHERE id=?", (ped_id,))


def marcar_recibido(ped_id):
    execute("UPDATE pedidos SET estado='recibido' WHERE id=?", (ped_id,))


# ─── Consumibles ──────────────────────────────────────────────────────────────

def get_consumibles():
    return fetchall(
        "SELECT c.*, s.codigo, s.descripcion, s.unidad, s.stock_actual "
        "FROM consumibles c JOIN skus s ON s.id=c.sku_id ORDER BY s.codigo"
    )


def get_consumible_by_sku(sku_id):
    return fetchone("SELECT * FROM consumibles WHERE sku_id=?", (sku_id,))


def upsert_consumible(sku_id, stock_seguridad, politica_seguridad,
                      politica_valor, modelo_lotificacion):
    execute(
        "INSERT INTO consumibles(sku_id,stock_seguridad,politica_seguridad,"
        "politica_valor,modelo_lotificacion) VALUES(?,?,?,?,?) "
        "ON CONFLICT(sku_id) DO UPDATE SET "
        "stock_seguridad=excluded.stock_seguridad,"
        "politica_seguridad=excluded.politica_seguridad,"
        "politica_valor=excluded.politica_valor,"
        "modelo_lotificacion=excluded.modelo_lotificacion",
        (sku_id, stock_seguridad, politica_seguridad, politica_valor, modelo_lotificacion)
    )


def delete_consumible(sku_id):
    execute("DELETE FROM consumibles WHERE sku_id=?", (sku_id,))


def get_alertas_stock():
    """SKUs (consumibles) cuyo stock_actual <= stock_seguridad."""
    return fetchall(
        "SELECT s.codigo, s.descripcion, s.unidad, s.stock_actual, "
        "c.stock_seguridad, c.politica_seguridad "
        "FROM consumibles c JOIN skus s ON s.id=c.sku_id "
        "WHERE s.stock_actual <= c.stock_seguridad "
        "ORDER BY (s.stock_actual - c.stock_seguridad)"
    )


# ─── BOM ──────────────────────────────────────────────────────────────────────

def get_bom(producto_id):
    return fetchall(
        "SELECT b.*, s.codigo AS comp_codigo, s.descripcion AS comp_desc "
        "FROM bom b JOIN skus s ON s.id=b.componente_id "
        "WHERE b.producto_id=? ORDER BY b.nivel, s.codigo",
        (producto_id,)
    )


def get_bom_full():
    return fetchall(
        "SELECT b.*, "
        "p.codigo AS prod_codigo, p.descripcion AS prod_desc, "
        "s.codigo AS comp_codigo, s.descripcion AS comp_desc "
        "FROM bom b "
        "JOIN skus p ON p.id=b.producto_id "
        "JOIN skus s ON s.id=b.componente_id "
        "ORDER BY p.codigo, b.nivel, s.codigo"
    )


def add_bom(producto_id, componente_id, cantidad, nivel=1, unidad="unidad"):
    return execute(
        "INSERT OR IGNORE INTO bom(producto_id,componente_id,cantidad,nivel,unidad) "
        "VALUES(?,?,?,?,?)",
        (producto_id, componente_id, cantidad, nivel, unidad)
    )


def update_bom(bom_id, cantidad, nivel, unidad):
    execute(
        "UPDATE bom SET cantidad=?,nivel=?,unidad=? WHERE id=?",
        (cantidad, nivel, unidad, bom_id)
    )


def delete_bom(bom_id):
    execute("DELETE FROM bom WHERE id=?", (bom_id,))


def explotar_bom(producto_id, cantidad_requerida=1):
    """
    Explota el BOM multi-nivel del producto.
    Retorna lista de {componente_id, codigo, descripcion, cantidad_total, nivel}.
    """
    items = {}

    def _recur(pid, qty, nivel):
        filas = get_bom(pid)
        for f in filas:
            cid = f["componente_id"]
            total_qty = qty * f["cantidad"]
            if cid in items:
                items[cid]["cantidad_total"] += total_qty
            else:
                items[cid] = {
                    "componente_id": cid,
                    "codigo":        f["comp_codigo"],
                    "descripcion":   f["comp_desc"],
                    "cantidad_total": total_qty,
                    "nivel":         f["nivel"],
                    "unidad":        f["unidad"],
                }
            # Recursión si el componente también tiene BOM
            sub = get_bom(cid)
            if sub:
                _recur(cid, total_qty, nivel + 1)

    _recur(producto_id, cantidad_requerida, 1)
    return sorted(items.values(), key=lambda x: (x["nivel"], x["codigo"]))


# ─── MPS ──────────────────────────────────────────────────────────────────────

def get_mps(sku_id=None):
    if sku_id:
        return fetchall(
            "SELECT m.*, s.codigo, s.descripcion FROM mps m "
            "JOIN skus s ON s.id=m.sku_id WHERE m.sku_id=? ORDER BY m.periodo",
            (sku_id,)
        )
    return fetchall(
        "SELECT m.*, s.codigo, s.descripcion FROM mps m "
        "JOIN skus s ON s.id=m.sku_id ORDER BY m.sku_id, m.periodo"
    )


def upsert_mps(sku_id, periodo, cantidad_planificada, cantidad_real=0):
    execute(
        "INSERT INTO mps(sku_id,periodo,cantidad_planificada,cantidad_real) "
        "VALUES(?,?,?,?) ON CONFLICT(sku_id,periodo) DO UPDATE SET "
        "cantidad_planificada=excluded.cantidad_planificada,"
        "cantidad_real=excluded.cantidad_real",
        (sku_id, periodo, cantidad_planificada, cantidad_real)
    )


def delete_mps(mps_id):
    execute("DELETE FROM mps WHERE id=?", (mps_id,))


# ─── Facturas ─────────────────────────────────────────────────────────────────

def _next_numero_factura() -> str:
    row = fetchone("SELECT COUNT(*) AS n FROM facturas")
    n = (row["n"] if row else 0) + 1
    return f"FAC-{datetime.now().year}-{n:04d}"


def get_facturas():
    return fetchall(
        "SELECT f.*, p.nombre AS proveedor_nombre "
        "FROM facturas f "
        "LEFT JOIN proveedores p ON p.id=f.proveedor_id "
        "ORDER BY f.fecha DESC, f.id DESC"
    )


def get_factura(fac_id):
    return fetchone(
        "SELECT f.*, p.nombre AS proveedor_nombre "
        "FROM facturas f "
        "LEFT JOIN proveedores p ON p.id=f.proveedor_id "
        "WHERE f.id=?",
        (fac_id,)
    )


def add_factura(proveedor_id, metodo_pago, notas="", fecha=None):
    numero = _next_numero_factura()
    fecha  = fecha or datetime.now().strftime("%Y-%m-%d")
    return execute(
        "INSERT INTO facturas(numero,fecha,proveedor_id,metodo_pago,notas,total) "
        "VALUES(?,?,?,?,?,0)",
        (numero, fecha, proveedor_id, metodo_pago, notas)
    )


def update_factura_total(fac_id):
    row = fetchone(
        "SELECT COALESCE(SUM(subtotal),0) AS t FROM factura_items WHERE factura_id=?",
        (fac_id,)
    )
    execute("UPDATE facturas SET total=? WHERE id=?", (row["t"] if row else 0, fac_id))


def delete_factura(fac_id):
    execute("DELETE FROM facturas WHERE id=?", (fac_id,))


# ─── Ítems de factura ─────────────────────────────────────────────────────────

def get_factura_items(fac_id):
    return fetchall(
        "SELECT fi.*, s.codigo AS sku_codigo, s.descripcion AS sku_desc "
        "FROM factura_items fi "
        "LEFT JOIN skus s ON s.id=fi.sku_id "
        "WHERE fi.factura_id=? ORDER BY fi.id",
        (fac_id,)
    )


def add_factura_item(fac_id, sku_id, cantidad, unidad, precio_unitario):
    subtotal = round(cantidad * precio_unitario, 4)
    item_id  = execute(
        "INSERT INTO factura_items(factura_id,sku_id,cantidad,unidad,precio_unitario,subtotal) "
        "VALUES(?,?,?,?,?,?)",
        (fac_id, sku_id, cantidad, unidad, precio_unitario, subtotal)
    )
    update_factura_total(fac_id)
    return item_id


def update_factura_item(item_id, sku_id, cantidad, unidad, precio_unitario):
    subtotal   = round(cantidad * precio_unitario, 4)
    item       = fetchone("SELECT factura_id FROM factura_items WHERE id=?", (item_id,))
    execute(
        "UPDATE factura_items SET sku_id=?,cantidad=?,unidad=?,precio_unitario=?,subtotal=? "
        "WHERE id=?",
        (sku_id, cantidad, unidad, precio_unitario, subtotal, item_id)
    )
    if item:
        update_factura_total(item["factura_id"])


def delete_factura_item(item_id):
    item = fetchone("SELECT factura_id FROM factura_items WHERE id=?", (item_id,))
    execute("DELETE FROM factura_items WHERE id=?", (item_id,))
    if item:
        update_factura_total(item["factura_id"])


def confirmar_factura_en_stock(fac_id):
    """Suma las cantidades de los ítems de la factura al stock de cada SKU."""
    for item in get_factura_items(fac_id):
        if item["sku_id"]:
            add_stock(item["sku_id"], item["cantidad"])

