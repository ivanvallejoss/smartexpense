"""
Factories para generar datos de prueba usando factory-boy.
"""
import factory
from django.utils import timezone
from apps.core.models import User, Category, Expense

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    # Secuencias aseguran que campos únicos nunca choquen entre tests
    telegram_id = factory.Sequence(lambda n: 1000000 + n)
    username = factory.Sequence(lambda n: f"testuser_{n}")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Categoría {n}")
    is_default = False
    color = "#FF5733"
    user = factory.SubFactory(UserFactory)


class ExpenseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Expense

    # SubFactory crea automáticamente un User y una Category si no se los pasamos
    user = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    
    amount = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True, min_value=1)
    description = factory.Faker("sentence", nb_words=4)
    # Usamos LazyFunction para que la fecha se evalúe al momento de crear el objeto, en el pasado
    date = factory.LazyFunction(timezone.now)