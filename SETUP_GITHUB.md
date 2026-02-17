# 📦 Guía Paso a Paso: Subir Nanobot a GitHub

## 🎯 Objetivo
Crear el repositorio privado **Moliendo-oro** en GitHub y subir el código de forma segura, **sin incluir credenciales ni archivos sensibles**.

---

## ⚠️ ADVERTENCIAS CRÍTICAS

> **❌ NUNCA SUBAS ESTOS ARCHIVOS:**
> - `config/credentials.json`
> - `.env`
> - `logs/` (completo)
> - `models/*.joblib` (pesados, se regeneran localmente)
> - Cualquier archivo con API keys

---

## 📋 Pre-requisitos

1. **Git instalado**: `git --version`
2. **GitHub CLI (opcional)**: `brew install gh` o usar la interfaz web
3. **Conexión a Internet**
4. **Cuenta de GitHub activa**

---

## 🚀 Paso 1: Preparar el Repositorio Local

### 1.1 Navegar al directorio del proyecto
```bash
cd /Users/danielsuarezsucre/TRADING/trading_agent
```

### 1.2 Verificar que .gitignore existe
```bash
cat .gitignore
```
✅ Debe existir y contener reglas para excluir credenciales, logs y modelos.

### 1.3 Inicializar Git (si no está inicializado)
```bash
git init
```

**Salida esperada:**
```
Initialized empty Git repository in /Users/danielsuarezsucre/TRADING/trading_agent/.git/
```

---

## 🔒 Paso 2: Verificar Seguridad (CRÍTICO)

### 2.1 Verificar qué archivos se van a subir
```bash
git status
```

### 2.2 Verificar que archivos sensibles están excluidos
```bash
git check-ignore -v config/credentials.json .env logs/
```

**Salida esperada:**
```
.gitignore:3:config/credentials.json    config/credentials.json
.gitignore:4:.env    .env
.gitignore:11:logs/    logs/
```

✅ Si ves estas líneas, los archivos están **correctamente excluidos**.

### 2.3 Listar archivos que SÍ se van a incluir
```bash
git add -n .
```

**Revisa la lista y asegúrate de que NO aparezcan:**
- `credentials.json`
- `.env`
- Archivos `.log`
- Modelos `.joblib` (excepto si usas Git LFS)

---

## 📝 Paso 3: Hacer el Commit Inicial

### 3.1 Añadir todos los archivos seguros
```bash
git add .
```

### 3.2 Revisar cambios staged
```bash
git status
```

### 3.3 Crear el commit inicial
```bash
git commit -F COMMIT_MESSAGE.txt
```

O si prefieres un mensaje más corto:
```bash
git commit -m "feat: Phase 22 - Institutional Kelly Sizing & Probabilistic Calibration

- Isotonic RF calibration (Brier: 0.165 → 0.101)
- Fractional Kelly engine (0.25x) with SE shrinkage
- FTMO-grade validation (Convexity: 3.15, P99 DD: -8.29%)
- Block bootstrap stress testing
- Risk overlay and circuit breakers"
```

---

## 🌐 Paso 4: Crear Repositorio en GitHub

### Opción A: GitHub CLI (Recomendado)

```bash
# 4.1 Autenticarse en GitHub
gh auth login

# 4.2 Crear repositorio privado
gh repo create Moliendo-oro \
  --private \
  --description "🦖 Nanobot - Institutional Trading System with AI Risk Management" \
  --source=. \
  --remote=origin \
  --push
```

✅ Esto crea el repo, lo vincula y sube el código automáticamente.

---

### Opción B: Interfaz Web de GitHub

**4.1** Ve a: https://github.com/new

**4.2** Configura:
- **Repository name**: `Moliendo-oro`
- **Description**: `🦖 Nanobot - Institutional Trading System`
- **Visibility**: ☑️ **Private**
- **Initialize**: ⬜ NO marques ninguna opción (ya tienes README local)

**4.3** Haz clic en **Create repository**

**4.4** Vincula el repositorio local:
```bash
git remote add origin https://github.com/Danielssucre/Moliendo-oro.git
```

**4.5** Verifica la conexión:
```bash
git remote -v
```

**4.6** Sube el código:
```bash
git branch -M main
git push -u origin main
```

---

## ✅ Paso 5: Verificación Post-Push

### 5.1 Comprobar que se subió correctamente
```bash
git log --oneline
```

### 5.2 Visitar el repositorio
```bash
open https://github.com/Danielssucre/Moliendo-oro
```

### 5.3 Verificar en GitHub que NO están los archivos sensibles:
- ❌ `config/credentials.json`
- ❌ `.env`
- ❌ `logs/`
- ✅ `.gitignore`
- ✅ `README.md`
- ✅ `.env.example`

---

## 🔄 Paso 6: Flujo de Trabajo Futuro

### Hacer cambios y subirlos
```bash
# 1. Modificar archivos
nano src/probability/kelly_sizing.py

# 2. Ver cambios
git status
git diff

# 3. Añadir cambios
git add src/probability/kelly_sizing.py

# 4. Commit
git commit -m "fix: Adjust Kelly fraction to 0.2x"

# 5. Push
git push
```

### Clonar en otra máquina
```bash
git clone https://github.com/Danielssucre/Moliendo-oro.git
cd Moliendo-oro

# Configurar entorno
cp .env.example .env
# Editar .env con tus credenciales

# Instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Entrenar modelos
python scripts/experimental/retrain_calibrated.py
```

---

## 🤔 FAQ: Gestión de Modelos y Credenciales

### ¿Debería usar Git LFS para los modelos?

**Recomendación: NO**

**Razones:**
1. Git LFS tiene límites de almacenamiento (1-2GB gratis)
2. Los modelos pueden regenerarse con scripts
3. Más simple mantener fuera de git

**Alternativa:** Sube solo los scripts de entrenamiento:
```bash
# El .gitignore ya excluye models/*.joblib
# Incluye el script para regenerarlos
git add scripts/experimental/retrain_calibrated.py
```

Cuando alguien clone el repo:
```bash
python scripts/experimental/retrain_calibrated.py
```

---

### ¿Cómo gestionar las credenciales de forma segura?

**Mejor práctica:**

1. **Nunca** commitear `credentials.json` o `.env`
2. Usar archivos de ejemplo:
   - `.env.example` ✅ (en git)
   - `.env` ❌ (excluido de git)
3. Documentar en README cómo configurar

**Configuración en nueva máquina:**
```bash
cp .env.example .env
nano .env  # Rellenar con tus claves reales
```

**Variables de entorno en scripts:**
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Carga .env
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
```

---

## 🛡️ Checklist Final de Seguridad

Antes de hacer `git push`, verifica:

- [ ] `.gitignore` está configurado correctamente
- [ ] `git status` no muestra archivos sensibles
- [ ] `.env.example` está incluido (sin claves reales)
- [ ] `credentials.example.json` está incluido (sin claves reales)
- [ ] `logs/` está excluido
- [ ] `models/*.joblib` están excluidos
- [ ] README.md documenta cómo configurar credenciales

---

## 📞 Troubleshooting

### Error: "remote: Repository not found"
```bash
# Verifica la URL
git remote -v

# Actualiza la URL si es incorrecta
git remote set-url origin https://github.com/Danielssucre/Moliendo-oro.git
```

### Error: "Permission denied (publickey)"
```bash
# Usa HTTPS en lugar de SSH
git remote set-url origin https://github.com/Danielssucre/Moliendo-oro.git

# O configura SSH keys
gh auth login
```

### Archivos sensibles ya commiteados por error
```bash
# ⚠️ PELIGRO: Reescribe historia
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config/credentials.json" \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all
```

**Mejor:** Contacta a GitHub Support para borrar el repositorio y empezar de cero.

---

## ✅ Resumen Ejecutivo

```bash
# Setup completo en 5 comandos
cd /Users/danielsuarezsucre/TRADING/trading_agent
git init
git add .
git commit -F COMMIT_MESSAGE.txt
gh repo create Moliendo-oro --private --source=. --remote=origin --push
```

¡Listo! Tu código está seguro en GitHub 🎉
