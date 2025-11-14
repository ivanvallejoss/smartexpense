# SmartExpense

Expense tracker inteligente con bot de Telegram para parsing automático de gastos.

## 🚀 Stack Tecnológico

- **Backend:** Django 5.0 + Django REST Framework
- **Database:** PostgreSQL 15
- **Cache/Queue:** Redis 7
- **Async Tasks:** Celery (próximamente)
- **Bot:** python-telegram-bot
- **Testing:** pytest + factory-boy
- **Code Quality:** black, isort, flake8, pre-commit

## 📋 Requisitos

- Python 3.11+
- Docker & Docker Compose
- Git

## 🛠️ Setup Inicial

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd smartexpense
```

### 2. Crear virtual environment
```bash
# Con pyenv (recomendado)
pyenv local 3.11.9
python -m venv venv
source venv/bin/activate

# O con Python del sistema
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install --upgrade pip
pip install psycopg2-binary  # Instalar primero separadamente
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus valores si es necesario
```

### 5. Levantar servicios Docker
```bash
# Iniciar PostgreSQL y Redis
docker compose up -d

# Verificar que estén corriendo
docker compose ps
```

### 6. Aplicar migraciones
```bash
python backend/manage.py migrate
```

### 7. Crear superuser
```bash
python backend/manage.py createsuperuser
```

### 8. Instalar pre-commit hooks
```bash
pre-commit install
```

## 🎯 Comandos Principales

### Desarrollo
```bash
# Levantar servidor de desarrollo
python backend/manage.py runserver

# Crear migraciones
python backend/manage.py makemigrations

# Aplicar migraciones
python backend/manage.py migrate

# Acceder a shell de Django
python backend/manage.py shell_plus
```

### Testing
```bash
# Correr todos los tests
pytest

# Con coverage
pytest --cov=backend --cov-report=html

# Ver reporte de coverage
open htmlcov/index.html
```

### Docker
```bash
# Levantar servicios
docker compose up -d

# Ver logs
docker compose logs -f

# Detener servicios
docker compose down

# Reiniciar servicios
docker compose restart

# Ver estado
docker compose ps
```

### Code Quality
```bash
# Formatear código (black)
black backend/

# Ordenar imports (isort)
isort backend/

# Linting (flake8)
flake8 backend/

# Correr todos los checks de pre-commit
pre-commit run --all-files
```

## 📁 Estructura del Proyecto
```
smartexpense/
├── backend/
│   ├── config/              # Configuración Django
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/
│   │   ├── core/            # Modelos principales
│   │   ├── api/             # API REST endpoints
│   │   ├── bot/             # Telegram bot
│   │   ├── parsers/         # Parseo de expenses
│   │   └── ml/              # Categorización ML
│   ├── tests/               # Tests de integración
│   └── manage.py
├── docker-compose.yml       # Servicios Docker
├── Dockerfile              # Imagen Docker
├── requirements.txt        # Dependencias Python
├── pyproject.toml         # Configuración herramientas
├── pytest.ini             # Configuración pytest
├── .pre-commit-config.yaml # Pre-commit hooks
├── .env.example           # Variables de entorno ejemplo
├── .gitignore
└── README.md
```

## 🔑 Acceso al Admin

Una vez levantado el servidor:

**URL:** http://127.0.0.1:8000/admin/

**Credenciales:** Las que creaste con `createsuperuser`

## 🐛 Troubleshooting

### Puerto 5432 ya en uso

Si tenés PostgreSQL instalado localmente, cambiá el puerto en `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Usar 5433 en lugar de 5432
```

Y actualizá `.env`:
```
DATABASE_URL=postgresql://smartexpense_user:smartexpense_pass@localhost:5433/smartexpense_db
```

### Problemas con psycopg2-binary

Si falla la instalación:
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev libpq-dev gcc

# Luego instalar
pip install psycopg2-binary
```

### Python no muestra output

Si `manage.py` no muestra nada, editá la primera línea de `backend/manage.py`:
```python
#!/usr/bin/env python -u
```

El flag `-u` fuerza unbuffered output.

## 📝 Próximos Pasos

- [ ] Implementar modelos de Expense, Category, User
- [ ] Crear endpoints REST API
- [ ] Configurar Telegram Bot
- [ ] Implementar parsers de texto
- [ ] Agregar categorización ML
- [ ] Setup Celery para tareas async
- [ ] Deploy en Railway

## 🤝 Contribución

Este es un proyecto educativo/portafolio. Las contribuciones son bienvenidas.

## 📄 Licencia

MIT

---

**Desarrollado por Ivan Vallejos** | Backend Developer
