"""
Evento canónico: la única forma en que el worker ve un mensaje entrante.

Se construye tipado en el productor y se encola como dict plano — el
contrato con ARQ y con el Bridge Go es un dict, no esta clase.
"""
from dataclasses import asdict, dataclass, field
from typing import Any

EVENT_MESSAGE = "message"
EVENT_CALLBACK = "callback"
EVENT_TYPES = (EVENT_MESSAGE, EVENT_CALLBACK)


class InvalidEvent(ValueError):
    """El evento no cumple el contrato mínimo."""


@dataclass
class ChannelEvent:
    channel: str
    external_user_id: str
    text: str
    message_id: str
    timestamp: int
    raw: dict[str, Any] = field(default_factory=dict)

    type: str = EVENT_MESSAGE
    conversation_id: str = ""
    edit_ref: str | None = None
    ack_ref: str | None = None
    profile: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.channel:
            raise InvalidEvent("channel es obligatorio")
        if not self.external_user_id:
            raise InvalidEvent("external_user_id es obligatorio")
        if not self.message_id:
            raise InvalidEvent("message_id es obligatorio")
        if self.type not in EVENT_TYPES:
            raise InvalidEvent(f"type inválido: {self.type!r}")

        # Normalización defensiva: los ids llegan como int desde los payloads.
        self.external_user_id = str(self.external_user_id)
        self.message_id = str(self.message_id)
        self.conversation_id = str(self.conversation_id or self.external_user_id)
        self.timestamp = int(self.timestamp)

    @property
    def is_callback(self) -> bool:
        return self.type == EVENT_CALLBACK

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelEvent":
        """
        Reconstruye desde el dict encolado.

        Lanza TypeError si el dict trae claves desconocidas — es intencional:
        detecta jobs en vuelo con un esquema viejo en vez de ignorarlos.
        """
        return cls(**data)


def job_id_for(event: ChannelEvent) -> str:
    """
    Clave de idempotencia para ARQ. Contrato: f"{channel}:{message_id}".
    Vive acá para que productor y tests no la escriban por separado.
    """
    return f"{event.channel}:{event.message_id}"
