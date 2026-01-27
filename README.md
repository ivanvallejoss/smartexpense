# SmartExpense

Expense tracker inteligente con bot de Telegram para parsing automático de gastos. Actualmente trabajando en el proyecto pero sin preparar bien el README.
Puedes encontrar mas informacion sobre mis avances, la configuracion del bot y como voy preparando todo en mi [blog](https://www.notion.so/ideavallejos/SmartExpense-2e027bfa15f580768e56ecae126c8836?source=copy_link)

## Stack Tecnológico

- **Backend:** Django 5.0 + Django REST Framework
- **Database:** PostgreSQL 15
- **Cache/Queue:** Redis 7
- **Async Tasks:** Celery
- **Bot:** python-telegram-bot
- **Testing:** pytest + factory-boy
- **Code Quality:** black, isort, flake8

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

## Próximos Pasos

- [ ] Crear endpoints REST API
- [ ]

## Contribución

Este es un proyecto educativo/portafolio. Las contribuciones son bienvenidas.

## Licencia

MIT

---

**Desarrollado por Ivan Vallejos** | Backend Developer
