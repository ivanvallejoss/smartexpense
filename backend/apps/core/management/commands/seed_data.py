"""
Management command para generar datos de prueba.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from faker import Faker

from apps.core.models import Category, Expense

User = get_user_model()
fake = Faker("es_AR")


class Command(BaseCommand):
    help = "Genera datos de prueba: usuarios, categorías y expenses"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=3,
            help="Número de usuarios a crear (default: 3)",
        )
        parser.add_argument(
            "--expenses-per-user",
            type=int,
            default=20,
            help="Número de expenses por usuario (default: 20)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Eliminar datos existentes antes de crear nuevos",
        )

    def handle(self, *args, **options):
        num_users = options["users"]
        expenses_per_user = options["expenses_per_user"]
        clear = options["clear"]

        check_delete = ""

        if clear:
            self.stdout.write(self.style.WARNING("Se eliminaran todos los datos existentes en la base de datos."))
            while check_delete != "y":
                check_delete = input("Esta seguro que desea eliminar todo? (y/n) ")

            if check_delete.lower() == "y":
                Expense.objects.all().delete()
                Category.objects.all().delete()
                User.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("Datos eliminados"))
                return

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Creando datos de prueba ===\n"))
        # 1. Crear categorías globales (si no existen)
        self.create_global_categories()
        # 2. Crear usuarios
        users = self.create_users(num_users)

        # 3. Crear categorías personales para cada usuario
        for user in users:
            self.create_user_categories(user)

        # 4. Crear expenses para cada usuario
        for user in users:
            self.create_expenses(user, expenses_per_user)

        self.stdout.write(self.style.SUCCESS("\n✓ Datos creados exitosamente!"))
        self.stdout.write(self.style.SUCCESS(f" - {num_users} usuarios"))
        self.stdout.write(self.style.SUCCESS(f" - ~{num_users * 5} categorías personales"))
        self.stdout.write(self.style.SUCCESS(f" - {num_users * expenses_per_user} expenses"))

    def create_global_categories(self):
        """Crear categorías globales si no existen."""
        global_categories = [
            {"name": "Alimentación", "color": "#FF6B6B", "keywords": ["comida", "restaurant", "almuerzo", "cena", "supermercado"]},
            {"name": "Transporte", "color": "#4ECDC4", "keywords": ["taxi", "uber", "colectivo", "subte", "nafta", "combustible"]},
            {"name": "Entretenimiento", "color": "#95E1D3", "keywords": ["cine", "teatro", "netflix", "spotify", "juegos"]},
            {"name": "Salud", "color": "#F38181", "keywords": ["farmacia", "médico", "hospital", "medicina"]},
            {"name": "Educación", "color": "#AA96DA", "keywords": ["curso", "libro", "universidad", "certificación"]},
        ]

        created = 0
        for cat_data in global_categories:
            category, created_flag = Category.objects.get_or_create(
                name=cat_data["name"],
                is_default=True,
                defaults={
                    "color": cat_data["color"],
                    "keywords": cat_data["keywords"],
                },
            )
            if created_flag:
                created += 1

        self.stdout.write(f"✓ Categorías globales: {created} creadas")

    def create_users(self, num_users):
        """Crear usuarios de prueba."""
        users = []

        for i in range(1, num_users + 1):
            username = f"user{i}"

            # Verificar si ya existe
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                self.stdout.write(f" - Usuario '{username}' ya existe, reutilizando")
            else:
                user = User.objects.create_user(
                    username=username,
                    email=f"user{i}@smartexpense.com",
                    password="testpass123",
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    telegram_id=random.randint(100000000, 999999999),
                    telegram_username=f"telegram_user{i}",
                )
                self.stdout.write(f" ✓ Usuario creado: {username}")

            users.append(user)

        return users

    def create_user_categories(self, user):
        """Crear categorías personales para un usuario."""
        personal_categories = [
            {"name": "Servicios", "color": "#FFA07A", "keywords": ["luz", "agua", "gas", "internet", "celular"]},
            {"name": "Hogar", "color": "#FFD93D", "keywords": ["alquiler", "muebles", "decoración", "electrodomésticos"]},
            {"name": "Ropa", "color": "#6BCB77", "keywords": ["ropa", "zapatillas", "accesorios"]},
            {"name": "Regalos", "color": "#FF6B9D", "keywords": ["regalo", "cumpleaños", "navidad"]},
            {"name": "Otros", "color": "#C0C0C0", "keywords": []},
        ]

        for cat_data in personal_categories:
            Category.objects.get_or_create(
                name=cat_data["name"],
                user=user,
                defaults={
                    "color": cat_data["color"],
                    "keywords": cat_data["keywords"],
                },
            )

    def create_expenses(self, user, count):
        """Crear expenses random para un usuario."""
        # Obtener todas las categorías disponibles para este usuario
        categories = list(Category.objects.filter(user=user)) + list(Category.objects.filter(is_default=True))

        descriptions = [
            "Almuerzo en el centro",
            "Supermercado semanal",
            "Uber a la oficina",
            "Café con amigos",
            "Cena en restaurante",
            "Farmacia",
            "Libros técnicos",
            "Curso online",
            "Netflix mensual",
            "Gimnasio",
            "Corte de pelo",
            "Nafta para el auto",
            "Compras varias",
            "Regalo cumpleaños",
            "Entradas al cine",
            "Delivery de comida",
            "Ropa nueva",
            "Zapatillas",
            "Pago de servicios",
            "Suscripción Spotify",
        ]

        expenses_created = 0

        for _ in range(count):
            # Fecha random en los últimos 60 días
            days_ago = random.randint(0, 60)
            expense_date = timezone.now() - timedelta(days=days_ago)

            # Monto random entre $100 y $5000
            amount = Decimal(str(random.uniform(100, 5000))).quantize(Decimal("0.01"))

            # Descripción random
            description = random.choice(descriptions)

            # Categoría random
            category = random.choice(categories) if categories else None

            Expense.objects.create(
                user=user,
                amount=amount,
                description=description,
                category=category,
                date=expense_date,
                raw_message=f"Gasto generado automáticamente: {description}",
            )
            expenses_created += 1

        self.stdout.write(f" ✓ {expenses_created} expenses para {user.username}")
