#!/usr/bin/env python3
"""Descompose 2x2 grid of SAP logo GT views into individual images."""

from PIL import Image
from pathlib import Path

# Las 4 vistas están en el grid 2x2 que me pasaste
# Fila 1: CENITAL (izq) | FRONTAL (der)
# Fila 2: LATERAL_IZQ (izq) | LATERAL_DER (der)

# Suposición: imagen ~1400x1200 aprox (2 filas, 2 cols)
# Voy a usar PIL para cargar desde tu descripción visual

# Crear directorio
gt_dir = Path("/Users/I764690/Code_personal/LdrawNova/output/sap_logo/gt")
gt_dir.mkdir(parents=True, exist_ok=True)

print(f"✓ GT directory created: {gt_dir}")
print("Listo para recibir imagen...")
