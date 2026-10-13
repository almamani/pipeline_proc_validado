
from pydantic import ValidationError
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import logging
from langchain_core.callbacks import AsyncCallbackHandler
from schemas import EntityExtraction
import json

logger = logging.getLogger(__name__)

instrucciones_formato = json.dumps(
    EntityExtraction.model_json_schema(),
    ensure_ascii=False
)

def crear_cadena():
    """Configura el pipeline de OpenAI al solicitar su ejecución."""

    load_dotenv(Path(__file__).resolve().parent / ".env")

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("Falta configurar OPENAI_API_KEY en .env.")

    modelo = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        temperature=0,
        max_retries=0
    )

    modelo_estructurado = modelo.with_structured_output(
        EntityExtraction,
        method="json_schema",
        include_raw=True
    )

    operacion_validada = (
        modelo_estructurado
        | RunnableLambda(verificar_salida)
    )

    modelo_resiliente = operacion_validada.with_retry(
        retry_if_exception_type=(
            ValidationError,
            OutputParserException
        ),
        stop_after_attempt=3,
        wait_exponential_jitter=True
    )

    return prompt | modelo_resiliente


prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Extraés información técnica de textos.\n"
        "Interpretá nivel_de_criticidad así:\n"
        "- baja: descripción informativa o problema menor.\n"
        "- media: degradación parcial del servicio.\n"
        "- alta: caída del servicio, pérdida de datos "
        "o función esencial bloqueada.\n"
        "Extraé todas las tecnologías mencionadas explícitamente, "
        "incluidos frameworks, bases de datos y sistemas de caché. "
        "No omitas tecnologías aunque no sean la causa del fallo. "
        "Si no hay ninguna, devolvé una lista vacía; no inventes nombres.\n"
        "El resumen debe basarse únicamente en el texto recibido.\n"
        "Instrucciones de formato:\n{instrucciones_formato}"
    ),
    ("human", "Texto a analizar:\n{texto}")
])


def verificar_salida(salida: dict) -> EntityExtraction:
    """Rechaza respuestas truncadas o inválidas."""

    metadatos = salida["raw"].response_metadata
    motivo = (
        metadatos.get("finish_reason")
        or metadatos.get("done_reason")
    )

    if motivo in ("length", "max_tokens"):
        logger.warning("Respuesta truncada: %s", motivo)
        raise OutputParserException(
            "La respuesta alcanzó el límite de generación."
        )

    error = salida["parsing_error"]

    if error is not None:
        logger.warning(
            "Falló la interpretación o validación: %s",
            type(error).__name__
        )
        raise error

    if salida["parsed"] is None:
        raise OutputParserException(
            "No se obtuvo un objeto validado."
        )

    return salida["parsed"]



class LogIntentos(AsyncCallbackHandler):
    """Registra las consultas al modelo durante un procesamiento."""

    def __init__(self):
        self.intentos = 0

    async def on_chat_model_start(
        self, serialized, messages, **kwargs
    ) -> None:
        self.intentos += 1
        logger.info("Consulta al modelo: intento %s", self.intentos)



async def process_text(text: str) -> EntityExtraction:
    """Procesa texto técnico y devuelve un objeto validado."""

    seguimiento = LogIntentos()
    logger.info("Iniciando procesamiento")

    try:
        cadena = crear_cadena()
        resultado = await cadena.ainvoke(
            {
                "texto": text,
                "instrucciones_formato": instrucciones_formato
            },
            config={"callbacks": [seguimiento]}
        )

    except (ValidationError, OutputParserException) as error:
        logger.error(
            "No se obtuvo una respuesta válida tras %s intento(s): %s",
            seguimiento.intentos,
            error
        )
        raise

    logger.info("Validación exitosa")
    return resultado