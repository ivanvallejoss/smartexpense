import pytest
from unittest.mock import patch, AsyncMock

@pytest.fixture(autouse=True)
def mock_redis_state():
    """
    Mockea las funciones de estado de Redis para todos los tests del bot.
    Sin esto, cualquier test que ejecute handle_message falla porque
    Redis no está disponible en el entorno de tests.
    """
    with patch(
        "apps.bot.handlers.handlers.get_pending_category_state",
        new=AsyncMock(return_value=None)
    ) as mock_get, patch(
        "apps.bot.handlers.handlers.clear_pending_category_state",
        new=AsyncMock(return_value=None)
    ) as mock_clear:
        yield {"get": mock_get, "clear": mock_clear}