"""
eoq_models.py — Modelos EOQ para sistema de inventarios
========================================================
Implementa las 5 variantes del modelo EOQ + modelos de lotificación MRP:
  1. InventarioEOQ         — EOQ Clásico
  2. EOQFaltantes          — EOQ con faltantes permitidos (backorders)
  3. RevisionPeriodica     — Modelo de revisión periódica (sistema P)
  4. InventarioSeguridadContinuo — Revisión continua con inventario de seguridad
  5. DescuentosCantidad    — EOQ con descuentos por cantidad (all-units)
  6. POQModel              — Period Order Quantity (lotificación por períodos)
  7. LoteXLote             — Lote por lote (pedido exacto por período)
"""

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


# ─── 1. EOQ Clásico ───────────────────────────────────────────────────────────

class InventarioEOQ:
    """
    Modelo EOQ Clásico con consumo constante.

    Parámetros
    ----------
    D  : Demanda anual (unidades/año)
    S  : Costo por pedido ($/pedido)
    H  : Costo de mantenimiento ($/unidad/año)
    P  : Precio unitario ($/unidad)          [opcional, default 0]
    L  : Lead time en días                   [opcional, default 0]
    SS : Inventario de seguridad (unidades)  [opcional, default 0]
    """

    nombre = "EOQ Clásico"

    def __init__(self, D, S, H, P=0.0, L=0.0, SS=0.0):
        self.D  = float(D)
        self.S  = float(S)
        self.H  = float(H)
        self.P  = float(P)
        self.L  = float(L)
        self.SS = float(SS)
        self._validar()

    def _validar(self):
        if self.D <= 0: raise ValueError("La demanda D debe ser > 0")
        if self.S <= 0: raise ValueError("El costo de pedido S debe ser > 0")
        if self.H <= 0: raise ValueError("El costo de mantenimiento H debe ser > 0")

    # ── Cálculos principales ────────────────────────────────────────────────

    def calcular_eoq(self) -> float:
        """Cantidad económica de pedido Q* = sqrt(2DS/H)"""
        return math.sqrt(2.0 * self.D * self.S / self.H)

    def calcular_costos(self) -> dict:
        """Retorna diccionario con Q*, costos y parámetros operativos."""
        Q = self.calcular_eoq()
        d = self.D / 365.0

        costo_pedidos      = (self.D / Q) * self.S
        costo_mantenimiento = (Q / 2.0 + self.SS) * self.H
        costo_compra       = self.D * self.P
        costo_total        = costo_pedidos + costo_mantenimiento + costo_compra

        return {
            "Q_optimo":           round(Q, 4),
            "num_pedidos_anio":   round(self.D / Q, 4),
            "tiempo_ciclo_dias":  round(Q / self.D * 365.0, 2),
            "punto_reorden":      round(d * self.L + self.SS, 4),
            "inventario_promedio":round(Q / 2.0 + self.SS, 4),
            "costo_pedidos":      round(costo_pedidos, 4),
            "costo_mantenimiento":round(costo_mantenimiento, 4),
            "costo_compra":       round(costo_compra, 4),
            "costo_total":        round(costo_total, 4),
        }

    def generar_calendario(self, fecha_inicio=None, num_periodos: int = 1) -> pd.DataFrame:
        """
        Genera el calendario de pedidos para `num_periodos` años.

        Returns
        -------
        DataFrame con columnas: Pedido #, Fecha de Pedido, Fecha de Entrega,
                                Cantidad (Q*), Lead Time (días)
        """
        if fecha_inicio is None:
            fecha_inicio = datetime.now().replace(hour=0, minute=0,
                                                  second=0, microsecond=0)
        Q         = self.calcular_eoq()
        ciclo     = Q / self.D * 365.0
        n_pedidos = math.ceil(num_periodos * 365.0 / ciclo)
        d_diaria  = self.D / 365.0

        filas = []
        for i in range(n_pedidos):
            f_ped = fecha_inicio + timedelta(days=i * ciclo)
            f_ent = f_ped + timedelta(days=self.L)
            inv_rec = round(self.SS + max(Q - d_diaria * self.L, 0), 1) if i > 0 \
                      else round(Q + self.SS, 1)
            filas.append({
                "Pedido #":          i + 1,
                "Fecha de Pedido":   f_ped.strftime("%Y-%m-%d"),
                "Fecha de Entrega":  f_ent.strftime("%Y-%m-%d"),
                "Cantidad (Q*)":     round(Q, 1),
                "Lead Time (días)":  int(self.L),
                "Inv. al recibir":   inv_rec,
            })
        return pd.DataFrame(filas)

    def serie_inventario(self, dias: int = 365):
        """
        Genera la serie de tiempo del nivel de inventario.

        Returns
        -------
        t   : array de tiempos (días)
        inv : array de niveles (unidades)
        """
        Q     = self.calcular_eoq()
        d     = self.D / 365.0
        ciclo = Q / d

        t   = np.linspace(0, dias, dias * 10)
        pos = t % ciclo
        inv = np.maximum(Q - d * pos + self.SS, self.SS)
        return t, inv

    def analisis_sensibilidad(self, param: str = "D", rango: float = 0.5,
                               puntos: int = 60):
        """
        Variación de Q* y costo total al cambiar ±rango% de un parámetro.

        Parameters
        ----------
        param  : "D", "S" o "H"
        rango  : fracción de variación (0.5 = ±50%)
        puntos : número de puntos

        Returns
        -------
        valores, Q_array, costo_array
        """
        base = {"D": self.D, "S": self.S, "H": self.H}
        val0 = base[param]
        valores = np.linspace(val0 * (1 - rango), val0 * (1 + rango), puntos)

        Q_arr, C_arr = [], []
        for v in valores:
            p = base.copy()
            p[param] = v
            Q = math.sqrt(2.0 * p["D"] * p["S"] / p["H"])
            C = (p["D"] / Q) * p["S"] + (Q / 2.0) * p["H"] + p["D"] * self.P
            Q_arr.append(Q)
            C_arr.append(C)

        return valores, np.array(Q_arr), np.array(C_arr)


# ─── 2. EOQ con Faltantes ─────────────────────────────────────────────────────

class EOQFaltantes(InventarioEOQ):
    """
    EOQ con faltantes permitidos (backorders).

    Parámetro adicional
    -------------------
    B : costo de faltante por unidad por año ($/unidad/año)
    """

    nombre = "EOQ con Faltantes"

    def __init__(self, D, S, H, B, P=0.0, L=0.0):
        super().__init__(D, S, H, P, L)
        self.B = float(B)
        if self.B <= 0:
            raise ValueError("El costo de faltante B debe ser > 0")

    def calcular_eoq(self) -> float:
        """Q* = sqrt(2DS/H) · sqrt((H+B)/B)"""
        return (math.sqrt(2.0 * self.D * self.S / self.H) *
                math.sqrt((self.H + self.B) / self.B))

    def calcular_costos(self) -> dict:
        Q     = self.calcular_eoq()
        S_max = Q * self.B / (self.H + self.B)   # inventario máximo
        F_max = Q - S_max                          # faltante máximo
        d     = self.D / 365.0

        c_ped  = (self.D / Q) * self.S
        c_man  = (S_max ** 2) / (2.0 * Q) * self.H
        c_fal  = (F_max ** 2) / (2.0 * Q) * self.B
        c_comp = self.D * self.P
        c_tot  = c_ped + c_man + c_fal + c_comp

        return {
            "Q_optimo":           round(Q, 4),
            "inventario_maximo":  round(S_max, 4),
            "faltante_maximo":    round(F_max, 4),
            "num_pedidos_anio":   round(self.D / Q, 4),
            "tiempo_ciclo_dias":  round(Q / self.D * 365.0, 2),
            "t1_inventario_dias": round(S_max / d, 2),
            "t2_faltante_dias":   round(F_max / d, 2),
            "costo_pedidos":      round(c_ped, 4),
            "costo_mantenimiento":round(c_man, 4),
            "costo_faltantes":    round(c_fal, 4),
            "costo_compra":       round(c_comp, 4),
            "costo_total":        round(c_tot, 4),
        }

    def serie_inventario(self, dias: int = 365):
        Q     = self.calcular_eoq()
        S_max = Q * self.B / (self.H + self.B)
        d     = self.D / 365.0
        ciclo = Q / d
        t1    = S_max / d

        t   = np.linspace(0, dias, dias * 10)
        pos = t % ciclo
        # Positivo = inventario; negativo = faltante
        inv = S_max - d * pos
        return t, inv

    def generar_calendario(self, fecha_inicio=None, num_periodos: int = 1):
        if fecha_inicio is None:
            fecha_inicio = datetime.now().replace(hour=0, minute=0,
                                                  second=0, microsecond=0)
        Q     = self.calcular_eoq()
        S_max = Q * self.B / (self.H + self.B)
        ciclo = Q / self.D * 365.0
        n     = math.ceil(num_periodos * 365.0 / ciclo)

        filas = []
        for i in range(n):
            f_ped = fecha_inicio + timedelta(days=i * ciclo)
            f_ent = f_ped + timedelta(days=self.L)
            filas.append({
                "Pedido #":           i + 1,
                "Fecha de Pedido":    f_ped.strftime("%Y-%m-%d"),
                "Fecha de Entrega":   f_ent.strftime("%Y-%m-%d"),
                "Q* Total":           round(Q, 1),
                "Inv. Máximo (S*)":   round(S_max, 1),
                "Faltante Máx.":      round(Q - S_max, 1),
            })
        return pd.DataFrame(filas)


# ─── 3. Revisión Periódica ────────────────────────────────────────────────────

class RevisionPeriodica(InventarioEOQ):
    """
    Modelo de revisión periódica — sistema P.

    El inventario se revisa cada T* días y se ordena hasta el nivel M.

    Parámetros adicionales
    ----------------------
    sigma_d : desviación estándar de la demanda diaria
    z       : factor de servicio (z-score), ej. 1.645 para 95%
    """

    nombre = "Revisión Periódica"

    def __init__(self, D, S, H, sigma_d, z=1.645, L=0.0, P=0.0):
        super().__init__(D, S, H, P, L)
        self.sigma_d = float(sigma_d)
        self.z       = float(z)

    def calcular_periodo_optimo(self) -> float:
        """T* (días) = sqrt(2S / (H · d))"""
        d = self.D / 365.0
        return math.sqrt(2.0 * self.S / (self.H * d))

    def calcular_inventario_seguridad(self, T=None) -> float:
        """SS = z · σ_d · sqrt(T + L)"""
        if T is None:
            T = self.calcular_periodo_optimo()
        return self.z * self.sigma_d * math.sqrt(T + self.L)

    def calcular_nivel_maximo(self, T=None) -> float:
        """M = d·(T+L) + z·σ_d·sqrt(T+L)"""
        if T is None:
            T = self.calcular_periodo_optimo()
        d = self.D / 365.0
        return d * (T + self.L) + self.z * self.sigma_d * math.sqrt(T + self.L)

    def calcular_eoq(self) -> float:
        """Cantidad esperada por período = d · T*"""
        return self.D / 365.0 * self.calcular_periodo_optimo()

    def calcular_costos(self) -> dict:
        T  = self.calcular_periodo_optimo()
        d  = self.D / 365.0
        Q  = d * T
        M  = self.calcular_nivel_maximo(T)
        SS = self.calcular_inventario_seguridad(T)

        c_ped  = (365.0 / T) * self.S
        c_man  = (Q / 2.0 + SS) * self.H
        c_comp = self.D * self.P

        return {
            "T_optimo_dias":          round(T, 2),
            "nivel_maximo_M":         round(M, 4),
            "inventario_seguridad":   round(SS, 4),
            "Q_esperado_por_periodo": round(Q, 4),
            "num_revisiones_anio":    round(365.0 / T, 2),
            "costo_pedidos":          round(c_ped, 4),
            "costo_mantenimiento":    round(c_man, 4),
            "costo_compra":           round(c_comp, 4),
            "costo_total":            round(c_ped + c_man + c_comp, 4),
        }

    def serie_inventario(self, dias: int = 365):
        T  = self.calcular_periodo_optimo()
        M  = self.calcular_nivel_maximo(T)
        SS = self.calcular_inventario_seguridad(T)
        d  = self.D / 365.0

        t   = np.linspace(0, dias, dias * 10)
        pos = t % T
        inv = np.maximum(M - d * pos, SS * 0.8)
        return t, inv

    def generar_calendario(self, fecha_inicio=None, num_periodos: int = 1):
        if fecha_inicio is None:
            fecha_inicio = datetime.now().replace(hour=0, minute=0,
                                                  second=0, microsecond=0)
        T  = self.calcular_periodo_optimo()
        M  = self.calcular_nivel_maximo(T)
        d  = self.D / 365.0
        n  = math.ceil(num_periodos * 365.0 / T)
        inv_aprox = M - d * T

        filas = []
        for i in range(n):
            f_rev = fecha_inicio + timedelta(days=i * T)
            f_ent = f_rev + timedelta(days=self.L)
            filas.append({
                "Revisión #":            i + 1,
                "Fecha de Revisión":     f_rev.strftime("%Y-%m-%d"),
                "Fecha de Entrega":      f_ent.strftime("%Y-%m-%d"),
                "Nivel Máximo (M)":      round(M, 1),
                "Inv. Aprox. al Revisar":round(max(inv_aprox, 0.0), 1),
                "Q Aprox. a Ordenar":    round(M - max(inv_aprox, 0.0), 1),
            })
        return pd.DataFrame(filas)


# ─── 4. Inventario de Seguridad — Revisión Continua ──────────────────────────

class InventarioSeguridadContinuo(InventarioEOQ):
    """
    Sistema Q con inventario de seguridad (revisión continua).

    Se calcula Q* con EOQ clásico y se añade un stock de seguridad
    basado en la variabilidad de la demanda durante el lead time.

    Parámetros adicionales
    ----------------------
    sigma_d : desviación estándar de la demanda diaria
    z       : factor de servicio (z-score)
    """

    nombre = "Inv. Seguridad (Rev. Continua)"

    def __init__(self, D, S, H, sigma_d, z=1.645, L=0.0, P=0.0):
        sigma_L = float(sigma_d) * math.sqrt(max(float(L), 1.0))
        SS      = float(z) * sigma_L
        super().__init__(D, S, H, P, L, SS)
        self.sigma_d = float(sigma_d)
        self.sigma_L = sigma_L
        self.z       = float(z)

    def calcular_costos(self) -> dict:
        Q   = self.calcular_eoq()
        ROP = self.D / 365.0 * self.L + self.SS

        c_ped  = (self.D / Q) * self.S
        c_man  = (Q / 2.0 + self.SS) * self.H
        c_comp = self.D * self.P

        return {
            "Q_optimo":            round(Q, 4),
            "inventario_seguridad":round(self.SS, 4),
            "punto_reorden":       round(ROP, 4),
            "sigma_lead_time":     round(self.sigma_L, 4),
            "nivel_servicio_z":    self.z,
            "num_pedidos_anio":    round(self.D / Q, 4),
            "tiempo_ciclo_dias":   round(Q / self.D * 365.0, 2),
            "inventario_promedio": round(Q / 2.0 + self.SS, 4),
            "costo_pedidos":       round(c_ped, 4),
            "costo_mantenimiento": round(c_man, 4),
            "costo_compra":        round(c_comp, 4),
            "costo_total":         round(c_ped + c_man + c_comp, 4),
        }


# ─── 5. Descuentos por Cantidad ───────────────────────────────────────────────

class DescuentosCantidad:
    """
    EOQ con descuentos por cantidad (all-units discount).

    Evalúa todos los rangos de descuento y selecciona el de menor costo total.

    Parámetros
    ----------
    D        : Demanda anual
    S        : Costo de pedido
    H_pct    : Costo de mantenimiento como fracción del precio (ej. 0.20)
    descuentos: lista de tuplas [(cantidad_min, precio), ...]
                ordenadas de menor a mayor cantidad_min
    """

    nombre = "Descuentos por Cantidad"

    def __init__(self, D, S, H_pct, descuentos):
        self.D       = float(D)
        self.S       = float(S)
        self.H_pct   = float(H_pct)
        self.descuentos = sorted(descuentos, key=lambda x: x[0])

    def calcular_eoq_por_rango(self) -> pd.DataFrame:
        """
        Retorna DataFrame con Q_EOQ, Q factible y costo total para cada rango.
        La fila con menor costo total queda marcada como 'Seleccionado'.
        """
        n      = len(self.descuentos)
        filas  = []

        for i, (min_q, precio) in enumerate(self.descuentos):
            H     = self.H_pct * precio
            Q_eoq = math.sqrt(2.0 * self.D * self.S / H)
            max_q = self.descuentos[i + 1][0] - 1 if i < n - 1 else float("inf")

            # Ajustar Q al rango factible
            if Q_eoq < min_q:
                Q_fact = min_q
            elif Q_eoq > max_q:
                Q_fact = None           # no factible en este rango
            else:
                Q_fact = Q_eoq

            if Q_fact is not None:
                costo = ((self.D / Q_fact) * self.S +
                         (Q_fact / 2.0) * H +
                         self.D * precio)
                filas.append({
                    "Precio Unitario": precio,
                    "Rango Q Min":     int(min_q),
                    "Rango Q Max":     int(max_q) if max_q != float("inf") else "∞",
                    "Q EOQ":           round(Q_eoq, 2),
                    "Q Factible":      round(Q_fact, 2),
                    "Costo Total":     round(costo, 2),
                    "Seleccionado":    False,
                })

        if filas:
            idx = min(range(len(filas)), key=lambda x: filas[x]["Costo Total"])
            filas[idx]["Seleccionado"] = True

        return pd.DataFrame(filas)

    def obtener_optimo(self):
        """Retorna la fila óptima como Series, o None si no hay solución."""
        df  = self.calcular_eoq_por_rango()
        sel = df[df["Seleccionado"]]
        return sel.iloc[0] if len(sel) > 0 else None

    def serie_inventario(self, dias: int = 365):
        opt = self.obtener_optimo()
        if opt is None:
            t = np.linspace(0, dias, dias * 10)
            return t, np.zeros_like(t)
        Q     = opt["Q Factible"]
        d     = self.D / 365.0
        ciclo = Q / d
        t     = np.linspace(0, dias, dias * 10)
        pos   = t % ciclo
        inv   = np.maximum(Q - d * pos, 0.0)
        return t, inv

    def generar_calendario(self, fecha_inicio=None, num_periodos: int = 1):
        if fecha_inicio is None:
            fecha_inicio = datetime.now().replace(hour=0, minute=0,
                                                  second=0, microsecond=0)
        opt = self.obtener_optimo()
        if opt is None:
            return pd.DataFrame()

        Q     = opt["Q Factible"]
        ciclo = Q / self.D * 365.0
        n     = math.ceil(num_periodos * 365.0 / ciclo)

        filas = []
        for i in range(n):
            f_ped = fecha_inicio + timedelta(days=i * ciclo)
            filas.append({
                "Pedido #":       i + 1,
                "Fecha de Pedido":f_ped.strftime("%Y-%m-%d"),
                "Cantidad (Q*)":  round(Q, 1),
                "Precio Unitario":opt["Precio Unitario"],
                "Costo del Pedido":round(Q * opt["Precio Unitario"], 2),
            })
        return pd.DataFrame(filas)


# ─── 6. POQ — Period Order Quantity ──────────────────────────────────────────

class POQModel:
    """
    Period Order Quantity (POQ).

    El período de pedido T se obtiene redondeando EOQ / demanda_por_período.
    Para cada período se ordena la suma de la demanda de los T períodos siguientes.

    Parámetros
    ----------
    D        : Demanda anual (unidades/año)
    S        : Costo por pedido ($/pedido)
    H        : Costo de mantenimiento ($/unidad/año)
    periodos : número de períodos por año (ej. 12 = mensual, 52 = semanal)
    demandas : lista/array de demandas por período (len == periodos),
               si None se asume demanda uniforme D/periodos
    """

    nombre = "POQ — Period Order Quantity"

    def __init__(self, D, S, H, periodos=12, demandas=None):
        self.D        = float(D)
        self.S        = float(S)
        self.H        = float(H)
        self.periodos = int(periodos)
        if demandas is not None:
            self.demandas = [float(x) for x in demandas]
        else:
            d_per = self.D / self.periodos
            self.demandas = [d_per] * self.periodos

    def calcular_T(self) -> int:
        """Número de períodos que cubre cada pedido."""
        d_per = self.D / self.periodos
        Q_eoq = math.sqrt(2.0 * self.D * self.S / self.H)
        T = max(1, round(Q_eoq / d_per))
        return T

    def calcular_plan(self) -> pd.DataFrame:
        """
        Genera el plan de lotificación POQ período a período.

        Returns
        -------
        DataFrame: Período, Demanda, Inv. Inicial, Pedido, Inv. Final, Costo Período
        """
        T   = self.calcular_T()
        n   = self.periodos
        inv = 0.0
        filas = []

        i = 0
        while i < n:
            pedido = sum(self.demandas[i: i + T])
            for j in range(i, min(i + T, n)):
                inv_ini = inv + (pedido if j == i else 0)
                demanda_j = self.demandas[j]
                inv_fin = max(inv_ini - demanda_j, 0)
                c_ped = self.S if j == i else 0
                c_man = inv_fin * (self.H / self.periodos)
                filas.append({
                    "Período":      j + 1,
                    "Demanda":      round(demanda_j, 2),
                    "Inv. Inicial": round(inv_ini, 2),
                    "Pedido":       round(pedido if j == i else 0, 2),
                    "Inv. Final":   round(inv_fin, 2),
                    "Costo Pedido": round(c_ped, 2),
                    "Costo Mant.":  round(c_man, 2),
                })
                inv = inv_fin
            i += T

        df = pd.DataFrame(filas)
        return df

    def calcular_costos_totales(self):
        df = self.calcular_plan()
        return {
            "T_periodos":       self.calcular_T(),
            "num_pedidos":      int((df["Pedido"] > 0).sum()),
            "costo_pedidos":    round(df["Costo Pedido"].sum(), 4),
            "costo_mant":       round(df["Costo Mant."].sum(), 4),
            "costo_total":      round(df["Costo Pedido"].sum() + df["Costo Mant."].sum(), 4),
        }

    def serie_inventario(self, dias: int = 365):
        """Aproximación continua del nivel de inventario POQ."""
        T    = self.calcular_T()
        d    = self.D / 365.0
        Q    = sum(self.demandas[:T])
        ciclo = T * (365.0 / self.periodos)

        t   = np.linspace(0, dias, dias * 10)
        pos = t % ciclo
        inv = np.maximum(Q - d * pos, 0.0)
        return t, inv


# ─── 7. Lote×Lote ─────────────────────────────────────────────────────────────

class LoteXLote:
    """
    Lotificación Lote por Lote (Lot-for-Lot / L×L).

    Se ordena exactamente la demanda de cada período. Minimiza el inventario
    pero maximiza los costos de pedido.

    Parámetros
    ----------
    S        : Costo por pedido ($/pedido)
    H        : Costo de mantenimiento ($/unidad/período)
    demandas : lista de demandas por período
    """

    nombre = "Lote × Lote"

    def __init__(self, S, H, demandas):
        self.S        = float(S)
        self.H        = float(H)
        self.demandas = [float(x) for x in demandas]

    def calcular_plan(self) -> pd.DataFrame:
        """
        Genera el plan período a período.

        Returns
        -------
        DataFrame: Período, Demanda, Inv. Inicial, Pedido, Inv. Final, Costo Período
        """
        filas = []
        inv   = 0.0
        for i, d in enumerate(self.demandas):
            pedido  = d  # Lote = demanda exacta
            inv_ini = inv + pedido
            inv_fin = max(inv_ini - d, 0)
            c_ped   = self.S if d > 0 else 0
            c_man   = inv_fin * self.H
            filas.append({
                "Período":      i + 1,
                "Demanda":      round(d, 2),
                "Inv. Inicial": round(inv_ini, 2),
                "Pedido":       round(pedido, 2),
                "Inv. Final":   round(inv_fin, 2),
                "Costo Pedido": round(c_ped, 2),
                "Costo Mant.":  round(c_man, 2),
            })
            inv = inv_fin
        return pd.DataFrame(filas)

    def calcular_costos_totales(self):
        df = self.calcular_plan()
        return {
            "num_pedidos":  int((df["Pedido"] > 0).sum()),
            "costo_pedidos": round(df["Costo Pedido"].sum(), 4),
            "costo_mant":    round(df["Costo Mant."].sum(), 4),
            "costo_total":   round(df["Costo Pedido"].sum() + df["Costo Mant."].sum(), 4),
        }
