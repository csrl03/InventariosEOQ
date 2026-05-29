# ProjectContext — Sistema de Inventarios EOQ

## Stack Tecnológico
- **Lenguaje**: Python 3.x
- **GUI**: tkinter + ttk (built-in)
- **Gráficos**: matplotlib (TkAgg backend)
- **Datos**: numpy, pandas
- **Persistencia actual**: ninguna (sin archivos de datos persistentes)
- **Dependencias**: `requirements.txt` → numpy>=1.24, pandas>=2.0, matplotlib>=3.7

## Estructura Actual
```
Inventario/
├── app_gui.py        # GUI completa (1010 líneas) — todas las pestañas EOQ
├── eoq_models.py     # Modelos de cálculo EOQ (600 líneas)
├── main.py           # Punto de entrada (llama app_gui.main)
├── requirements.txt
└── test_import.py
```

## Arquitectura Detectada
- **Patrón**: Módulo único de GUI + módulo de modelos matemáticos
- **TabBase**: clase base para pestañas EOQ (panel izq + panel der con sub-tabs)
- **EOQApp**: clase principal que ensambla el Notebook con 5 tabs EOQ
- **Sin capa de datos persistentes** (todo en memoria durante ejecución)

## Paleta de Colores (paleta `C`)
```python
C = {
    "bg":       "#1a2a3a",   # fondo principal (azul oscuro)
    "panel":    "#243447",   # paneles
    "input_bg": "#2d3f52",   # campos de entrada
    "boton":    "#2980b9",   # botón primario
    "boton_h":  "#3498db",   # hover botón
    "verde":    "#27ae60",   # acentos, subtítulos
    "texto":    "#ecf0f1",   # texto principal
    "dim":      "#95a5a6",   # texto secundario
    "inv":      "#3498db",   # línea de inventario en gráficas
    "ss":       "#e74c3c",   # stock de seguridad (rojo)
    "rop":      "#f39c12",   # punto de reorden (naranja)
    "grid":     "#2c3e50",   # grillas de gráficas
    "graf_bg":  "#1a2a3a",   # fondo de gráficas
}
```

## Fuentes
```python
F_TITULO = ("Segoe UI", 13, "bold")
F_LABEL  = ("Segoe UI", 10)
F_BOLD   = ("Segoe UI", 10, "bold")
F_BOTON  = ("Segoe UI", 10, "bold")
F_MONO   = ("Consolas", 10)
F_SMALL  = ("Segoe UI", 9)
```

## Convenciones de Código
- Naming: `snake_case` para funciones/variables, `PascalCase` para clases
- Prefijo `v` para StringVars de campos de entrada (ej. `self.vD`, `self.vS`)
- Prefijo `_` para métodos/atributos privados
- Helper `_entry_row()` para crear filas label+entry
- Helper `_flt()` para validar y convertir StringVar a float
- Métodos de TabBase: `_crear_inputs`, `_fila_boton`, `_calcular`, `_graficar_inventario`, `_mostrar_calendario`, `_graficar_sensibilidad`

## Modelos EOQ Existentes
1. `InventarioEOQ` — EOQ Clásico
2. `EOQFaltantes` — EOQ con backorders
3. `RevisionPeriodica` — Sistema P
4. `InventarioSeguridadContinuo` — Revisión continua + SS
5. `DescuentosCantidad` — EOQ con descuentos all-units

## Navegación
- `tk.Tk` → `EOQApp` → `ttk.Notebook` principal con tabs
- Cada tab hereda de `TabBase(ttk.Frame)`
- Sub-notebook derecho con 4 sub-tabs: Inventario | Calendario | Resultados | Sensibilidad

## Patrones UI Recurrentes
- `ttk.Treeview` con style `Cal.Treeview` para tablas
- `FigureCanvasTkAgg` para insertar matplotlib
- `NavigationToolbar2Tk` para toolbar de gráficas
- `ttk.Scrollbar` acoplada a Treeview y Text widgets
- Botón exportar CSV en paneles de calendario
