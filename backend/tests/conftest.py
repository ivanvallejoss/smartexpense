import pytest
from ninja.testing import TestAsyncClient
from apps.api.views import api

@pytest.fixture(scope="session")
def ninja_client():
    return TestAsyncClient(api)