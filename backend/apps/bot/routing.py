"""
Parseo de comandos. Reemplaza a CommandHandler y context.args de PTB.
El router de despacho se agrega acá en la Fase 4b.
"""


def split_command(text: str) -> tuple[str | None, list[str]]:
    """
    Separa "/history 15" en ("history", ["15"]).

    Replica el parseo de PTB, incluido el sufijo @BotName que Telegram
    agrega en grupos: "/stats@SmartExpenseBot" → ("stats", []).

    Returns:
        (None, []) si el texto no es un comando.
    """
    if not text or not text.startswith("/"):
        return None, []

    partes = text.strip().split()
    comando = partes[0][1:].split("@", 1)[0].lower()

    if not comando:
        return None, []

    return comando, partes[1:]
