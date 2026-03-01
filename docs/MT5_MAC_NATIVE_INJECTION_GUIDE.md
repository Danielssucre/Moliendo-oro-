# Guía de Recuperación: Inyección Nativa de MetaTrader 5 en macOS (M1/M2/M3)

Esta documentación describe la **"Solución de Inyección IDE"**, diseñada para sobreponerse a fallos irreparables entre Wine 9.0+, Docker (Colima) y la librería `MetaTrader5` de Python en ecosistemas Apple Silicon. 

## 🚨 El Problema (Síntoma del Sábado a las 7 AM)
- **Docker Roto:** La imagen de Docker (`siliconmt5`) o el emulador Wine actualizaron paquetes subyacentes, lo que corrompió irreparablemente las tuberías de comunicación (IPC) en Linux.
- **Congelamiento:** El síntoma principal era que `mt5.initialize()` provocaba que el hilo de Python se congelara permanentemente, no arrojaba ningún error y devolvía *Timeout* al conectarse remotamente desde el Mac.
- **Fallo del Puente Básico:** Intentar usar directamente el binario nativo de Mac (CrossOver MetaTrader 5) con un precompilador de Python fallaba por la misma razón, pues Wine para Mac corta el acceso de subprocesos cuando se invocan APIs de Inter-Process Communication (IPC) desde un terminal falso.

---

## 🆚 Método Antiguo (Docker) vs. Nuevo Método (Inyección Nativa)

**Método Antiguo (`siliconmt5` con Docker/Colima):**
- **Arquitectura:** Requería una máquina virtual completa de Linux corriendo dentro de macOS (vía Colima), la cual a su vez usaba Wine para emular Windows y ejecutar MetaTrader 5.
- **Conexión:** El bot (`run_live.py`) se conectaba desde el Mac hacia este contenedor aislado usando mapeo de puertos de red.
- **Desventajas:** Muy pesado para la CPU. Extremadamente frágil ante actualizaciones. Cualquier ligero cambio en Linux, Docker o Wine 9.0 provocaba que las tuberías de comunicación (IPC) se rompieran, causando que MetaTrader ignorara los comandos y se congelara permanentemente.

**Nuevo Método (Inyección IDE Nativa):**
- **Arquitectura:** Elimina Docker por completo. Utiliza la aplicación MetaTrader 5 nativa que ya tienes instalada en tu Mac (la cual usa CrossOver ligero en el fondo).
- **Conexión:** Un motor de Python "invisible" vive dentro de la misma memoria de MetaTrader 5. Se ejecuta automáticamente y comparte la misma sesión gráfica.
- **Ventajas:** Mucho más rápido, consume menos RAM y batería. Al no cruzar barreras de red ni de máquinas virtuales pesadas, los comandos de la API (como `mt5.initialize()`) se ejecutan a nivel nativo, siendo inmune a las desconexiones o bloqueos IPC ("Timeouts") que destruían al método antiguo.

---

## 🛠️ La Solución Suprema (Inyección por MetaEditor)
Para evadir la muralla de aislamiento de memoria gráfica de CrossOver, la solución consiste en **inyectar un servidor de Python puro desde el interior de MetaTrader 5**, usando un botón oficial del software para que herede todos los permisos como si fuera parte del programa.

### Paso 1: Configurar Python "Embeddable" Remero
No usamos instaladores ni `brew`. Descargamos la versión ultra-ligera y directa de *Python 3.9 Embeddable* para Windows (`python-3.9.13-embed-amd64.zip`) y la descomprimimos DENTRO de la carpeta donde MetaTrader guarda sus binarios en tu disco Mac:

```bash
# Directorio destino en el Mac (Tu prefijo de Wine para MT5)
~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/
```

### Paso 2: Hackear MetaEditor64
La aplicación MT5 tiene un botón llamado **"IDE" (o presionar F4)** que abre el `metaeditor64.exe`. 
1. Renombramos el `metaeditor64.exe` original a `metaeditor64.exe.bak`.
2. Renombramos nuestro flamante `python.exe` (el de la versión Embeddable) a `metaeditor64.exe`.

De esta forma, al pulsar "IDE" en MetaTrader, **estaremos abriendo Python con privilegios de administrador del sistema gráfico sin que Mac / Wine lo sepan.**

### Paso 3: El Archivo Auto-Cargable (`.pth`)
Como Python Embeddable no ejecuta scripts por defecto a menos que se le pasen como argumentos, usamos la característica de los archivos `_pth` de Python en Windows.
Creamos un archivo llamado `metaeditor64._pth` en esa misma carpeta, conteniendo lo siguiente:

```text
python39.zip
.
Lib\site-packages

# Import automático al arrancar
import site
import rpyc_start
```
*Nota importante:* Agregar `Lib\site-packages` repara el error de "módulo no encontrado" que causa que la ventana se cierre de golpe al principio.

### Paso 4: El Payload (`rpyc_start.py`)
Creamos el archivo `rpyc_start.py` allí mismo. Este script levanta el servidor invisible RPyC en el puerto **18812** y se queda atrapado en un bucle infinito para mantener a Python vivo. (Por eso se abre y se queda una ventanita de comandos oscura detrás).

```python
import sys
from rpyc.utils.server import ThreadedServer
from rpyc.core.service import ClassicService

def run_server():
    print("Iniciando RPyC Classic Server en puerto 18812...")
    config = {'allow_all_attrs': True, 'allow_public_attrs': True, 'sync_request_timeout': 60}
    server = ThreadedServer(ClassicService, port=18812, protocol_config=config)
    server.start()

run_server()
```

---

## 🛡️ Adaptación del Bot (`run_live.py`)
Dado que el servidor ahora es nativo pero la librería de Python choca buscando el proceso `terminal64` explícito o encuentra la barrera de autenticación (`Error -6`), el Bot tuvo que ser parcheado. 

En `run_live.py`, cuando inicializamos a través del puerto, DEBEMOS pasar las credenciales estricta e instantáneamente. 

**Implementación Crítica en `run_live.py`:**
```python
mt5 = MetaTrader5(port=8001) # El Mac hace "port forwarding" de 8001 a 18812 localmente o se reconecta
mt5.initialize(
    path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', 
    portable=True, 
    login=1512629315, 
    password="TU_PASSWORD_AQUI", 
    server="FTMO-Demo"
)
```

## 🔄 ¿Cómo Recuperar el Sistema si Falla en el Futuro?
1. Cerciórate de que tu clave dinámica de FTMO `.env` o `credentials.json` concuerde con la que tiene el código de `run_live.py` en la llamada `initialize`.
2. Abre la app nativa de MetaTrader 5 en tu Mac.
3. Arriba, en la barra de herramientas, dale click al botón amarillo de **"IDE"**.
4. ¡Lista! Aparecerá una ventanita negra minimizable. Ese es tu servidor en el puerto 18812. 
5. Ejecuta `nohup ./keep_alive.sh &` y el bot operará maravillas de nuevo.
