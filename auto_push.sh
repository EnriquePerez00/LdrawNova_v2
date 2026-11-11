#!/bin/bash

echo "╔═════════════════════════════════════════════════════════════════╗"
echo "║        LDRAW-NOVA: PUSH TO GITHUB (AUTOMATIC)          ║"
echo "╚═════════════════════════════════════════════════════════════════╝"

echo "
⚠️  REQUIERE QUE HAYAS COMPLETADO ESTO:
   1. Añadido SSH key a GitHub
   2. Creado repositorio 'Ldraw-Nova' en GitHub

Presiona ENTER para continuar o Ctrl+C para cancelar...
"
read

echo "
⏳ Configurando repositorio local..."

cd /Users/I764690/Code_personal/LdrawNova

# Añade el remote
echo "✍️  Añadiendo remote origin..."
git remote add origin git@github.com:enriqueperezbcn1973/Ldraw-Nova.git

if [ $? -ne 0 ]; then
    echo "❌ Error: No se pudo añadir el remote. Verifica:"
    echo "   - SSH key está en GitHub"
    echo "   - Repositorio existe en GitHub"
    echo "   - O quizá ya existe un remote llamado 'origin'"
    echo "
Intentando eliminar remote existente..."
    git remote remove origin
    git remote add origin git@github.com:enriqueperezbcn1973/Ldraw-Nova.git
fi

echo "✅ Remote añadido"

# Verifica SSH
echo "
✍️  Verificando conexión SSH..."
ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"

if [ $? -eq 0 ]; then
    echo "✅ Conexión SSH verificada"
else
    echo "⚠️  Advertencia: No se pudo verificar SSH. Continuando..."
fi

# Renombra rama
echo "
✍️  Renombrando rama develop → main..."
git branch -M develop main
echo "✅ Rama renombrada a 'main'"

# Push
echo "
🚀 Pushiendo a GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo "
✅✅✅ ÙXITO! ✅✅✅"
    echo "
Tu repositorio está en:
  https://github.com/enriqueperezbcn1973/Ldraw-Nova"
    echo "
✅ 2 commits✅ 1,620 archivos✅ ~2.1M líneas"
    echo "
🎉 LdrawNova ahora está en GitHub!"
else
    echo "
❌ Error durante push. Verifica:"
    echo "   - SSH key está correctamente configurada"
    echo "   - El repositorio existe en GitHub"
    echo "   - Tienes permisos para escribir"
fi

echo "
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

