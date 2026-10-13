import asyncio

from chain import process_text

import logging

from pydantic import ValidationError
from langchain_core.exceptions import OutputParserException


async def main():
    texto = (
    "La API desarrollada con FastAPI utiliza Redis como caché "
    "y PostgreSQL para persistir datos. PostgreSQL dejó de aceptar "
    "conexiones y la API no puede guardar pedidos."
)

    try:
        resultado = await process_text(texto)

    except (ValidationError, OutputParserException):
        print("El procesamiento terminó sin una salida válida.")

    else:
        print("El modelo devolvió:")
        print(resultado.model_dump_json(indent=2))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s"
    )
    asyncio.run(main())