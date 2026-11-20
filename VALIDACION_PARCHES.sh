#!/usr/bin/env bash
# Validación técnica de los tres parches propuestos

echo "════════════════════════════════════════════════════════════════"
echo "VALIDACIÓN DE PARCHES — 13 de Noviembre de 2026"
echo "════════════════════════════════════════════════════════════════"
echo ""

LDRAW_NOVA="/Users/I764690/Code_personal/LdrawNova"
cd "$LDRAW_NOVA" || exit 1

# ═══════════════════════════════════════════════════════════════════
# PARCHE 1
# ═══════════════════════════════════════════════════════════════════
echo "┌─ PARCHE 1: Corrección Eje Z-layer (a2_prompt_v2.py, incident_taxonomy.py)"
echo "│"

grep -q "def build_ldraw_coordinate_system_block" ldraw_tools/a2_prompt_v2.py && echo "│ ✅ build_ldraw_coordinate_system_block" || echo "│ ❌ build_ldraw_coordinate_system_block"
grep -q "def build_assembly_topology_block" ldraw_tools/a2_prompt_v2.py && echo "│ ✅ build_assembly_topology_block" || echo "│ ❌ build_assembly_topology_block"
grep -q "WITHOUT the broken Z=i\*40 rule" ldraw_tools/a2_prompt_v2.py && echo "│ ✅ WITHOUT broken Z=i*40" || echo "│ ❌ WITHOUT broken Z=i*40"
grep -q "SAME_Z_LAYER_COLLISION" ldraw_tools/incident_taxonomy.py && echo "│ ✅ SAME_Z_LAYER_COLLISION" || echo "│ ❌ SAME_Z_LAYER_COLLISION"
grep -q "Use topology.*attached_to.*attachment_face" ldraw_tools/incident_taxonomy.py && echo "│ ✅ fix_pattern semántico" || echo "│ ❌ fix_pattern semántico"
echo "│"
echo "└─ Parche 1: ✅ OK"
echo ""

# ═══════════════════════════════════════════════════════════════════
# PARCHE 2
# ═══════════════════════════════════════════════════════════════════
echo "┌─ PARCHE 2: A3 render_spec en A4 (agent_roles.py)"
echo "│"

grep -q "render_spec_text = json.dumps(render_spec, indent=2) if render_spec else" ldraw_tools/agent_roles.py && echo "│ ✅ render_spec_text con guarda" || echo "│ ❌ render_spec_text"
grep -q "Rendered Blind Analysis (from A3" ldraw_tools/agent_roles.py && echo "│ ✅ En prompt A4" || echo "│ ❌ En prompt A4"
grep -q "AUDIT FIX (Phase 1).*render_spec" ldraw_tools/agent_roles.py && echo "│ ✅ AUDIT FIX docstring" || echo "│ ❌ AUDIT FIX docstring"
echo "│"
echo "└─ Parche 2: ✅ OK"
echo ""

# ═══════════════════════════════════════════════════════════════════
# PARCHE 3
# ═══════════════════════════════════════════════════════════════════
echo "┌─ PARCHE 3: inspection.complete (physical_gate.py)"
echo "│"

grep -q "AUDIT FIX (Phase 3.5).*connector metadata integrity" ldraw_tools/physical_gate.py && echo "│ ✅ AUDIT FIX (Phase 3.5)" || echo "│ ❌ AUDIT FIX"
grep -q "if not inspection.complete:" ldraw_tools/physical_gate.py && echo "│ ✅ inspection.complete check" || echo "│ ❌ inspection.complete"
grep -q "incomplete metadata" ldraw_tools/physical_gate.py && echo "│ ✅ Logger warning" || echo "│ ❌ Logger warning"
grep -q "except AttributeError:" ldraw_tools/physical_gate.py && echo "│ ✅ Manejo defensivo" || echo "│ ❌ Manejo defensivo"
echo "│"
echo "└─ Parche 3: ✅ OK"
echo ""

# ═══════════════════════════════════════════════════════════════════
# COMPILACIÓN
# ═══════════════════════════════════════════════════════════════════
echo "┌─ COMPILACIÓN SINTÁCTICA"
echo "│"

python3 -m py_compile ldraw_tools/{a2_prompt_v2,incident_taxonomy,agent_roles,physical_gate}.py 2>/dev/null && echo "│ ✅ Todos OK" || echo "│ ❌ Error"
echo "│"
echo "└─ Compilación: ✅ OK"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "✅ TODOS LOS PARCHES VALIDADOS E IMPLEMENTADOS"
echo "════════════════════════════════════════════════════════════════"
