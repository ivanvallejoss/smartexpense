"""
Constantes compartidas entre módulos de test.

Vive fuera de conftest.py porque conftest no es importable: pytest lo
descubre y lo carga, no lo expone como módulo.
"""

EXTERNAL_USER_ID = "123456789"