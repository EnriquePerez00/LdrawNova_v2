# Antigravity Rules: LdrawNova Domain Routing

## Step 0: Multimodal Profile Detection & Domain Routing

Cuando el usuario inicie una petición (con imagen, texto o ambos), antes de planificar o buscar piezas en `jev-rerank`, clasifica el input en uno de los perfiles registrados en `profiles/`:

| Señal de Entrada (Visual y Semántica) | Perfil Destino | Artefactos y Reglas Inyectadas |
| :--- | :--- | :--- |
| **Busto / Retrato / Rostro Humano**: Imagen muestra rostro humano, retrato o escultura de cabeza/hombros, O el texto menciona "busto", "retrato", "cara", "cabeza", "head", "portrait", "face". | `profiles/bust_hd/` | Carga **exclusivamente** `profiles/bust_hd/instructions_bust_hd.md`, `profiles/bust_hd/catalog/bust_whitelist.json` y `profiles/bust_hd/helpers/bust_engine.py`. |
| **Star Wars / Sci-Fi / Naves / Mechas**: Imagen muestra naves, cazas espaciales, vehículos sci-fi o mechas. | `profiles/starwars/` | Carga `profiles/starwars/` (o flujo espacial en sección 2 de `instructions.md`). |
| **Ambigüedad (Cascos / Personajes blindados / Droides)**: El input combina dos dominios (ej. busto de un droide o casco sci-fi) y el usuario no ha especificado el perfil con `@perfil`. | Pregunta en 1 línea | Pregunta **en 1 sola línea** antes de generar `plan.json`: *"¿Prefieres un paradigma constructivo de Escultura por capas (`@bust_hd`) o de Panelado angular (`@starwars_scifi`)?"* |

### Persistencia del Perfil en `plan.json`
Registra siempre el perfil seleccionado en el encabezado del archivo `.plan.json`:
```json
{
  "version": 1,
  "author": "LdrawNova Profile Engine",
  "profile": "bust_hd",
  "sections": [...]
}
```
Todas las sub-iteraciones de código Python (`generate.py`, `grid_builder.py`) deben mantener el mismo `PYTHONPATH` (`profiles/<perfil>/helpers`) y catálogo restringido del perfil activo.
