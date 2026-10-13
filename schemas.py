from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

class NivelDeCriticidad(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"

class EntityExtraction(BaseModel):
    tecnologias: list[str] = Field(
       min_length=1,
       description="Tecnologías mencionadas explícitamente en el texto."
    )
    
    nivel_de_criticidad: NivelDeCriticidad = Field(
       description="Gravedad del problema técnico: baja, media o alta."
    )

    resumen_tecnico: str = Field(
        min_length=10,
        description="Resumen técnico basado únicamente en el texto recibido."
    )

    @field_validator("tecnologias")
    @classmethod
    def validate_tecnologias(cls, valor: list[str]) -> list[str]:
        nombres = [nombre.strip() for nombre in valor]

        genericos = {"sistema", "software", "tecnología", "tecnologias"}

        if any(not nombre for nombre in nombres):
            raise ValueError("Los nombres de tecnologías no pueden estar vacíos.")
       

        if any(nombre.casefold() in genericos for nombre in nombres):
            raise ValueError(
                "Se requieren nombres concretos de tecnologías, "
                "no términos genéricos."
            )

        return nombres