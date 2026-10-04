# Local Data Logger — Complemento para NVDA

**Versión:** 1.1.0  
**Autor:** Agustin Martinez  
**Licencia:** GNU GPL v2  
**Compatibilidad:** NVDA 2026.1 o superior  

---

## ¿Qué es Local Data Logger?

Local Data Logger es un complemento para el lector de pantalla [NVDA](https://www.nvaccess.org/) que permite capturar los valores de campos de formulario (inputs, checkboxes, listas desplegables, etc.) en cualquier aplicación accesible y guardarlos automáticamente en archivos de texto locales con una organización diaria.

Está especialmente pensado como **respaldo ante fallos de conectividad o de servidor**: cuando un sistema en línea no está disponible, el operador puede seguir registrando las gestiones en local y luego volcar la información cuando la conexión se restaure.

Funciona tanto en **navegadores web** (Chrome, Firefox, Edge, etc.) como en **aplicaciones nativas de Windows** que sean accesibles a través de la API de accesibilidad.

---

## Características principales

- **Marcado de campos por contexto:** Cada campo marcado queda asociado al contexto donde vive (URL del sitio web o aplicación + título de ventana). Al cambiar de sitio o de formulario, los conjuntos de marcas son independientes.
- **Registro en modo *append*:** Los datos se añaden al archivo del día sin sobreescribir nada. El archivo sigue el formato `AAAA-MM-DD.txt`.
- **Sin tráfico de red:** Todo ocurre localmente; no se envía ningún dato a servidores externos.
- **Retroalimentación audible:** Beeps y mensajes de voz confirman cada acción (marcar, desmarcar, registrar).
- **Opciones configurables:** el pitido y el anuncio al enfocar un campo marcado se activan o desactivan en **NVDA → Preferencias → Opciones → Local Data Logger**.
- **Panel de gestión completo:** Permite revisar, renombrar y eliminar campos marcados, configurar el directorio de salida y abrir la carpeta de registros directamente desde NVDA.

---

## Atajos de teclado

| Acción | Atajo |
|---|---|
| Marcar el campo actualmente enfocado | `NVDA + Shift + M` |
| Quitar la marca del campo enfocado | `NVDA + Shift + U` |
| Registrar la gestión actual (capturar todos los campos marcados) | `NVDA + Shift + R` |
| Abrir el panel de gestión | `NVDA + Shift + L` |
| Anunciar la ruta del archivo de registro del día | `NVDA + Shift + P` |

> Los atajos pueden modificarse desde **NVDA → Preferencias → Gestos de entrada → Local Data Logger**.

---

## Flujo de trabajo típico

1. **Marcar campos:** Navega hasta cada campo del formulario que quieras registrar y presiona `NVDA + Shift + M`. NVDA anunciará «Objeto marcado para registro» y emitirá un doble beep ascendente. Al volver a enfocar ese campo en el futuro, un beep te recordará que está marcado.

2. **Registrar una gestión:** Una vez completado el formulario, presiona `NVDA + Shift + R`. El complemento recorre todos los campos marcados en ese contexto, captura sus valores actuales y los añade al archivo del día. Si algún campo marcado no se encuentra en pantalla, se registra como `[no encontrado]` y NVDA lo avisa.

3. **Revisar el registro:** Los archivos se guardan en `Documentos\LocalDataLogger\` (o la carpeta que hayas configurado) con el nombre `AAAA-MM-DD.txt`. Puedes abrirlos con cualquier editor de texto.

---

## Formato del archivo de registro

```
FECHA: 2026-05-21
Aplicación: chrome
URL: https://ejemplo.com/formulario
------------------------------------------
HORA: 10:15:32
Nombre: Juan Pérez
Número de expediente: 12345
Observaciones: Sin novedad
------------------------------------------
HORA: 10:21:07
Nombre: María García
Número de expediente: 67890
Observaciones: Requiere seguimiento
------------------------------------------
Aplicación: notepad - Sin título
------------------------------------------
HORA: 10:30:44
Nota: Llamada pendiente
------------------------------------------
```

- La primera línea del archivo del día es la fecha (solo aparece una vez).
- La cabecera de contexto (`Aplicación:` y, en navegadores, `URL:`) solo se escribe cuando es distinta de la **última** cabecera del archivo. Las gestiones consecutivas en el mismo sitio o ventana quedan bajo una única cabecera. Si se vuelve a un sitio anterior después de registrar en otro, su cabecera se repite para que no haya dudas sobre a qué sitio pertenece cada gestión.
- Cada gestión empieza con `HORA:` y termina con una línea de guiones.
- Los campos de texto vacíos se registran vacíos; las casillas se registran como `marcado` / `no marcado`.
- Si el archivo del día ya existe, los nuevos bloques se añaden al final.

> **Privacidad:** los registros se guardan en texto plano, sin cifrar. Si contienen datos personales o sensibles, guárdalos en una carpeta protegida y elimínalos cuando ya no sean necesarios.

---

## Panel de gestión (`NVDA + Shift + L`)

El panel permite:

- **Seleccionar el contexto** (sitio web o ventana) del que se quieren gestionar las marcas.
- **Ver los campos marcados** en ese contexto, con su etiqueta y nombre del elemento.
- **Renombrar la etiqueta** de un campo para que el registro sea más descriptivo.
- **Quitar un campo individual** o **vaciar todos los campos** de un contexto o de todos los contextos.
- **Configurar el directorio de salida** donde se guardan los archivos `.txt` diarios.
- **Abrir el directorio de registros** en el Explorador de Windows.

---

## Instalación

1. Descarga el archivo `localDataLogger1.1.0.nvda-addon`.
2. Abre el archivo con NVDA (doble clic o Intro sobre él).
3. Acepta la instalación cuando NVDA lo solicite.
4. Reinicia NVDA si se te pide.

---

## Desinstalación

Ve a **NVDA → Herramientas → Administrar complementos**, selecciona *Local Data Logger* y pulsa **Eliminar**.

---

## Estructura del repositorio

```
addon/                     ← Código fuente del complemento
  globalPlugins/
    localDataLogger/
      __init__.py          ← Punto de entrada, atajos y lógica principal
      addonConfig.py       ← Opciones guardadas en nvda.ini
      elementRegistry.py   ← Registro persistente de campos marcados (JSON)
      fileWriter.py        ← Escritura de archivos diarios en modo append
      managementDialog.py  ← Diálogo de gestión (wxPython)
      settingsPanel.py     ← Panel en Preferencias → Opciones
  doc/
    en/readme.html         ← Documentación (inglés; por ahora, copia de la española)
    es/readme.html         ← Documentación en español
  manifest.ini             ← Metadatos del complemento
  LICENSE.txt              ← Licencia GNU GPL v2
tests/                     ← Tests unitarios (no requieren NVDA)
build.py                   ← Genera el archivo .nvda-addon
```

---

## Desarrollo

```
python -m unittest discover -s tests   # tests
python build.py                        # genera localDataLogger<versión>.nvda-addon
```

GitHub Actions ejecuta los tests y genera el `.nvda-addon` en cada push.

---

## Requisitos

- Windows 10 o superior
- NVDA 2026.1 o superior

---

## Licencia

Este complemento se distribuye bajo la **Licencia Pública General de GNU versión 2** (GNU GPL v2). Consulta el archivo `LICENSE.txt` incluido en el complemento para más detalles.

---

## Nota sobre el proceso de desarrollo

Durante el desarrollo de este complemento se utilizaron herramientas de inteligencia artificial para mejorar la eficiencia del proceso y la calidad del código. Estas herramientas contribuyeron a la revisión de la arquitectura, la generación de patrones de código accesible y la verificación de buenas prácticas, permitiendo un ciclo de desarrollo más ágil y un resultado más robusto.
