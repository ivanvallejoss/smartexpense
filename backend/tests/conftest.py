import pytest
from ninja.testing import TestAsyncClient
from apps.api.views import api

@pytest.fixture(scope="module")
def ninja_client():
    return TestAsyncClient(api)
