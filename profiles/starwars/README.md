# Perfil de Dominio: Naves LEGO Star Wars (`profiles/starwars/`)

Módulo de dominio especializado de **LdrawNova** para la concepción, ingeniería aeronáutica paramétrica y validación CAD de **Naves, Cazas y Vehículos de LEGO Star Wars**.

Este perfil integra el dataset extraído de **Brickclinic** con **948 sets oficiales de Star Wars** ($\ge 2004$) y su inventario de **2.837 piezas** y **79 colores**.

---

## 1. Arquitectura "Core-and-Armor" en 8 Submodelos

1. `01_spine_chassis.ldr`: Chasis y viga central Technic resistente a la flexión (`component_count = 1`).
2. `02_cockpit_canopy.ldr`: Módulo de mando, consola y cúpula transparente.
3. `03_fuselage_armor.ldr`: Paneles de blindaje superior e inferior fijados con brackets SNOT.
4. `04_wings_port.ldr`: Ala izquierda (babor) con cuñas quirales Left.
5. `05_wings_starboard.ldr`: Ala derecha (estribor) reflejada sagitalmente con cuñas quirales Right (`mirror_wing_to_starboard()`).
6. `06_engine_nacelles.ldr`: Motores concéntricos con discos invertidos y toberas luminosas.
7. `07_greebling_trenches.ldr`: Trincheras mecánicas de servicio con fondo oscuro (Dark Bluish Grey `72`) y relieve (Light Bluish Grey `71`).
8. `08_display_stand.ldr`: Soporte expositor negro tipo UCS.

---

## 2. Catálogos y Datos Extraídos (`profiles/starwars/catalog/`)

* `starwars_whitelist.json`: 2.837 piezas categorizadas por subsistemas (Chasis Technic, Cuñas quirales, Slopes curvados, SNOT Brackets, Greebling, Motores, Canopies, Láseres).
* `starwars_palette.json`: Paletas por facción (Imperio Galáctico, Alianza Rebelde, Cazarrecompensas, República Galáctica) con ratios de sombreado óptico.
* `starwars_sets_summary.json`: Metadatos de los 948 sets analizados (año, piezas, nombre, tema).
* `starwars_part_color_combos.json`: Índice de 9.274 combinaciones (pieza, color) verificadas en sets reales para garantizar que nunca se proponga una pieza en un color inexistente.
