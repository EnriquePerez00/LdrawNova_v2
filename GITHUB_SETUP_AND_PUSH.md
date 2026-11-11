# 🚀 Setup GitHub y Push

## SSH Key Generada

✅ Se ha generado una clave SSH Ed25519 para tu cuenta:

```
Localización: ~/.ssh/id_ed25519
Public Key:
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBUiDOBkOqUCN1eVRUEvGK5X1xtXdVn97N4Y+IolIs/6 enriqueperezbcn1973@gmail.com
```

---

## PASO 1️⃣: Añadir SSH Key a GitHub

### 1. Copia tu clave pública
Va está copiada arriba. La encuentras en: `~/.ssh/id_ed25519.pub`

### 2. Ve a GitHub Settings
```
https://github.com/settings/keys
```

### 3. New SSH Key
- Click en **"New SSH key"**
- Title: `LdrawNova-MacBook`
- Key type: Authentication Key
- Pega tu clave pública
- Click **"Add SSH key"**

### 4. Verifica SSH connection
```bash
ssh -T git@github.com
```
Debería devolver:
```
Hi enriqueperezbcn1973! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## PASO 2️⃣: Crear Repositorio en GitHub

### 1. Ve a crear nuevo repo
```
https://github.com/new
```

### 2. Rellena los campos:
- **Repository name**: `Ldraw-Nova`
- **Description**: `Full 5-agent LEGO improvement loop with VLM, LLM, validators, and rendering`
- **Visibility**: Public
- ❌ **NO marques** "Initialize this repository with:"

### 3. Click "Create repository"

---

## PASO 3️⃣: Push Local Repository a GitHub

Una vez que hayas creado el repositorio en GitHub, ejecuta:

```bash
cd /Users/I764690/Code_personal/LdrawNova

# Añade el remote
git remote add origin git@github.com:enriqueperezbcn1973/Ldraw-Nova.git

# Renombra rama develop a main (si prefieres)
git branch -M develop main

# Push al servidor
git push -u origin main
```

---

## PASO 4️⃣: Verifica el Push

```bash
# Ver branches remotos
git branch -a

# Ver log
git log --oneline -5

# Abre en navegador
https://github.com/enriqueperezbcn1973/Ldraw-Nova
```

---

## ⚠️ Si hay problemas

### SSH Key no conecta
```bash
# Verifica la conexión SSH
ssh -vT git@github.com

# Si falla, asegúrate que la clave está en ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

### Rama develop no existe localmente
```bash
git branch -a  # Ver todas las ramas
git checkout develop  # Si existe
```

### Remote ya existe
```bash
git remote remove origin
git remote add origin git@github.com:enriqueperezbcn1973/Ldraw-Nova.git
```

---

## ✅ Completo!

Una vez completado, tu repositorio estará en:
```
https://github.com/enriqueperezbcn1973/Ldraw-Nova
```

🎉 **Todos los 2 commits, 1,620 archivos y ~2.1M líneas de código estarán en GitHub!**

