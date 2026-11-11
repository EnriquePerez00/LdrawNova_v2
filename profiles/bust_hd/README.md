# Perfil de Dominio: Bustos Humanos de Alta Definición (`profiles/bust_hd/`)

Módulo de dominio especializado de **LdrawNova** para la concepción, escultura computacional paramétrica y validación CAD de **Bustos Humanos de Alta Definición (de hombros hacia arriba)** en LEGO/LDraw.

---

## 1. Arquitectura "Core-and-Cladding"

El perfil implementa una arquitectura en tres niveles físicos para evitar figuras planas o endebles:

1. **Tier 1 (Núcleo y Columna Continua):**
   - Pedestal arquitectónico de museo (plinth) y hombros en corte trapezoidal.
   - Núcleo craneal continuo, trabado (cross-bonded) e indivisible desde el cuello hasta el vértex parietal (`component_count = 1`).
   - Apilado vertical estricto cumpliendo la ley física LDraw:
     $$y_{\text{upper}} = y_{\text{lower}} - \text{body\_height}$$
2. **Tier 2 (Anclajes SNOT Estandarizados):**
   - El núcleo expone puntos de anclaje periféricos (`87087.dat`, `11211.dat`, `4733.dat`, brackets `99207.dat`/`99780.dat`) mapeados en el diccionario paramétrico `ANCHOR_MAP`.
3. **Tier 3 (Piel Epidérmica y Micro-Detalle en SNOT):**
   - Acabado liso sin espárragos crudos visibles usando curved slopes (`11477`, `50950`, `15068`) y tiles lisos (`3069b`, `3068b`).
   - **Regla SNOT:** Ojos, tabique nasal, bermellón de labios y arcos superciliares se modelan con placas horizontales SNOT logrando una resolución vertical de **8 LDU por plate** (en vez del salto tosco de 24 LDU de un ladrillo estándar).

---

## 2. Estructura de Submodelos MPD (Los 7 Submodelos Oficiales)

Todo busto generado bajo este perfil se estructura en un archivo maestro `.mpd` dividido en 7 subensambles independientes:

| Archivo Submodelo | Función Anatómica | Anclaje Principal |
| :--- | :--- | :--- |
| `01_base_shoulders_neck.ldr` | Pedestal, pecho, hombros, escote y cuello | `base` ($h=0$ a $h=192$) |
| `02_cranium_structural_core.ldr` | Núcleo estructural craneal trabado con adaptadores | Base cervical ($h=192+$) |
| `03_jaw_beard_mouth.ldr` | Mandíbula, labios, mentón y textura de barba | `ANCHOR_JAW_CHIN_MOUTH` |
| `04_cheekbones_midface.ldr` | Pómulos simétricos y relieve malar | `ANCHOR_CHEEKBONES_L_R` |
| `05_nose_bridge_snot.ldr` | Tabique nasal, dorso y punta de queso 30° | `ANCHOR_NOSE_BRIDGE` |
| `06_eyes_brows_forehead.ldr` | Esclerótica blanca, iris, pupila, cejas y frente | `ANCHOR_EYES_BROW` |
| `07_ears_and_hair_sculpture.ldr` | Pabellones auriculares y casquete capilar | `ANCHOR_EARS_L_R`, `ANCHOR_HAIR_CAP` |

---

## 3. Guía de Uso Paso a Paso: Desde una Fotografía al Render CAD

### Paso 1: Activar el Perfil e Inspeccionar el Entorno
Ejecuta el script lanzador para comprobar rutas y dependencias:
```sh
source .venv/bin/activate
export LDRAW_DIR=$HOME/LDraw
export PATH=$HOME/.local/bin:$PATH

python profiles/bust_hd/activate_profile.py
```

### Paso 2: Extracción Fisonómica (Foto -> `facial_blueprint.json`)
Crea el directorio de trabajo para tu diseño (ej. `output/mi-retrato/`) e inicializa el blueprint:
```sh
python profiles/bust_hd/activate_profile.py --init-blueprint output/mi-retrato/facial_blueprint.json
```
Abre la imagen del sujeto e introduce en `facial_blueprint.json` los parámetros biométricos (proporciones faciales, forma de la mandíbula, densidad y colores de barba, prominencia de la nariz, color del iris y tipo de cuello). Si una zona está oculta en la foto, reconstrúyela mediante simetría sagital ($X = 0$).

### Paso 3: Generación del Código Python (`generate.py`)
Crea `output/mi-retrato/generate.py` importando `bust_engine.py`:
```python
from profiles.bust_hd.helpers.bust_engine import (
    AnatomicalCoreBuilder,
    generate_elliptical_layer,
    mirror_feature_x,
    apply_beard_or_hair_texture,
    SNOT_FRONT, SNOT_LEFT, SNOT_RIGHT,
)

builder = AnatomicalCoreBuilder("mi_retrato", "Retrato Humano HD")
builder.build_pedestal_and_shoulders(...)
builder.build_cranium_core(...)
# ... ensamble de submodelos ...
plan = builder.export_plan()
```

### Paso 4: Compilación CAD, Inspección y Renderizado
Compila y valida la geometría del modelo:
```sh
# 1. Compilar el plan JSON en MPD
./ldraw-agent build --output output/mi-retrato/mi_retrato.mpd output/mi-retrato/mi_retrato.plan.json

# 2. Validar colisiones y geometría (debe reportar 0 errores y 0 body overlaps)
./ldraw-agent validate --geometry --contacts all output/mi-retrato/mi_retrato.mpd

# 3. Renderizar vistas multiángulo (Home, Front, Top) mediante LeoCAD
./ldraw-agent render output/mi-retrato/mi_retrato.mpd --outdir output/mi-retrato/renders
```

---

## 4. Ejecución del Test Suite Canónico

Para verificar que todos los anclajes, matrices de rotación y piezas del catálogo cumplen con el validador estricto sin solapamientos:
```sh
python profiles/bust_hd/activate_profile.py --test
```
El test compila `canonical_bust.mpd`, verifica la orientación de los 344 componentes y asegura **0 errores de colisión** de cuerpos rectangulares.
