# Preentrega 2 — Pipeline de procesamiento validado

Pipeline de extracción de información técnica para Coderhouse AI Engineering. Recibe un párrafo y devuelve un objeto `EntityExtraction` validado con Pydantic, mediante una cadena LCEL asíncrona con OpenAI.

## Archivos del repositorio

| Archivo | Función |
| --- | --- |
| `schemas.py` | Modelo Pydantic, enum de criticidad y validadores. |
| `chain.py` | Prompt, cliente OpenAI, salida estructurada, control de metadatos, reintentos y `process_text()`. |
| `prueba_pipeline.py` | Mini-script de prueba asíncrono. |
| `requirements.txt` | Dependencias del proyecto. |
| `.env.example` | Plantilla de configuración sin credenciales. |
| `.gitignore` | Excluye credenciales, entorno virtual y cachés. |
| `README.md` | Instalación, ejecución y resultados de pruebas. |

El archivo `.env` se utiliza localmente y no forma parte del repositorio.

## Contrato y flujo

- `tecnologias`: lista con al menos un nombre. Se eliminan espacios exteriores y se rechazan nombres vacíos y ciertos términos genéricos definidos en el validador.
- `nivel_de_criticidad`: enum con `baja`, `media` y `alta`.
- `resumen_tecnico`: texto con un mínimo de 10 caracteres.

El prompt asigna criticidad baja a información o problemas menores, media a degradación parcial y alta a caída de servicio, pérdida de datos o funciones esenciales bloqueadas. Pide extraer todas las tecnologías explícitas y resumir sin agregar información.

El template utiliza roles system/human y las variables `texto` e `instrucciones_formato`. Las instrucciones se generan desde `EntityExtraction.model_json_schema()`.

La composición LCEL conecta el prompt con `ChatOpenAI.with_structured_output(EntityExtraction, method="json_schema", include_raw=True)` y un `RunnableLambda` que verifica la salida. Este control revisa metadatos de truncamiento, propaga `parsing_error` y devuelve el objeto validado.

La consulta estructurada y su verificación se envuelven juntas con `.with_retry()`: hasta **tres intentos totales** ante `ValidationError` u `OutputParserException`, con backoff exponencial y jitter. `max_retries=0` desactiva los reintentos internos del cliente. Esta política no incluye errores de transporte de OpenAI.

`process_text(text: str) -> EntityExtraction` ejecuta la cadena con `.ainvoke()`. Los logs muestran inicio, consultas al modelo, validación exitosa y fallo final. El cliente se crea al llamar a la función; importar el módulo no necesita una API key.

## Instalación en Windows / PowerShell

Requiere Python 3.12, una API key de OpenAI, acceso al modelo configurado y facturación habilitada.

Desde la carpeta del proyecto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completar `OPENAI_API_KEY` únicamente en `.env`:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

El archivo `.env` se lee junto a `chain.py`. No publicar la clave en Git ni en capturas o logs. Las consultas reales consumen saldo de la API.

## Ejecución

```powershell
.\.venv\Scripts\python.exe prueba_pipeline.py
```

El script contiene un texto técnico de ejemplo, llama a `process_text()` y muestra el objeto como JSON. Captura errores de validación o interpretación e informa si no se obtiene una salida válida.

Si falta `OPENAI_API_KEY`, se produce un `ValueError` de configuración; el script actual no captura este error y muestra su traceback. Los errores de autenticación o conexión tampoco se manejan como errores de validación.

## Pruebas reales con OpenAI

Realizadas el **13 de octubre de 2026**, con `gpt-4o-mini`.

### Caso normal

Texto configurado en `prueba_pipeline.py`:

> La API desarrollada con FastAPI utiliza Redis como caché y PostgreSQL para persistir datos. PostgreSQL dejó de aceptar conexiones y la API no puede guardar pedidos.

Resultado observado después de actualizar el validador:

```json
{
  "tecnologias": ["FastAPI", "Redis", "PostgreSQL"],
  "nivel_de_criticidad": "alta",
  "resumen_tecnico": "La API desarrollada con FastAPI utiliza Redis como caché y PostgreSQL para persistir datos. Actualmente, PostgreSQL ha dejado de aceptar conexiones, lo que impide que la API pueda guardar pedidos."
}
```

Los logs mostraron un intento, HTTP 200 y validación exitosa.

### Prueba de estrés: texto ambiguo

Para reproducirla, reemplazar temporalmente la asignación de `texto` en `main()` de `prueba_pipeline.py` por:

```python
texto = "Algo funciona mal, pero no sé qué sistema utiliza."
```

Ejecutar el mismo comando. Después de probar, puede restaurarse el texto normal.

Con el validador actualizado, se observaron tres consultas HTTP exitosas y ninguna salida válida. La última respuesta incluyó `tecnologias=[""]`, rechazada por el validador. Los logs y el script informaron:

```text
ERROR | chain | No se obtuvo una respuesta válida tras 3 intento(s): ...
El procesamiento terminó sin una salida válida.
```

Este rechazo es esperado para el contrato elegido: el texto no aporta una tecnología concreta y el esquema exige al menos una. El caso normal volvió a ejecutarse después del cambio del validador y pasó en un intento.

## Comprobaciones auxiliares realizadas durante el desarrollo

Estas comprobaciones se realizaron con scripts auxiliares que no se incluyen en la entrega:

- **Esquema:** aceptación de un caso con una tecnología y criticidad alta; rechazo de lista vacía, nombre vacío y criticidad no permitida.
- **Reintentos simulados:** respuesta sin JSON, respuesta incompleta y respuesta válida; recuperación en el tercer intento mediante `PydanticOutputParser` y `.with_retry()`. Esta prueba verifica el patrón y no reemplaza la ejecución real del pipeline.
- **Truncamiento simulado:** `verificar_salida()` rechazó `done_reason="length"` y `finish_reason="length"`, incluso con un objeto válido adjunto. No se provocó truncamiento real en OpenAI.

La versión preliminar se probó con Ollama local, pero el código entregado utiliza exclusivamente OpenAI y no requiere instalar Ollama ni descargar un modelo local.

## Límites

Pydantic valida estructura y restricciones; no demuestra exactitud, completitud ni fidelidad factual. El filtro de términos genéricos es acotado y no detecta todas las posibles invenciones.

Con `include_raw=True`, LangChain intenta interpretar la respuesta antes de que `verificar_salida()` inspeccione los metadatos. Nuestro control impide aceptar y devolver una respuesta marcada como truncada; no evita ese intento interno de interpretación.

El pipeline propaga el fallo final y no genera datos de reemplazo para hacer pasar una entrada insuficiente como válida. Las respuestas del modelo pueden variar entre ejecuciones.
