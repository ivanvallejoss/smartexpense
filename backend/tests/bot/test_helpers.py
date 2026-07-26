"""
Tests de construcción de opciones. Verifican los ids de callback y el
layout de filas, que es lo que define la experiencia visible del usuario.
"""
from apps.bot.handlers.helpers import (
    category_selection_options,
    correction_options,
    delete_options,
    undo_options,
)


class TestOpcionesSimples:

    def test_delete(self):
        filas = delete_options(expense_id=55)
        assert len(filas) == 1
        assert filas[0][0].label == "Eliminar"
        assert filas[0][0].id == "del:55"

    def test_undo(self):
        filas = undo_options(deleted_object_id=99)
        assert filas[0][0].label == "↩️ Deshacer borrado"
        assert filas[0][0].id == "undo:99"

    def test_correccion_dos_opciones_en_una_fila(self):
        filas = correction_options(expense_id=55)
        assert len(filas) == 1
        assert [o.id for o in filas[0]] == ["cat_confirm:55", "cat_list:55"]


class TestSeleccionDeCategorias:

    class _Cat:
        def __init__(self, id, name):
            self.id, self.name = id, name

    def test_ids_incluyen_expense_y_categoria(self):
        filas = category_selection_options(55, [self._Cat(3, "Comida")])
        assert filas[0][0].id == "cat_select:55:3"
        assert filas[0][0].label == "Comida"

    def test_nueva_categoria_siempre_sola_al_final(self):
        """
        Con 3 categorías: [2, 1, 1]. Si 'Nueva' entrara en el grid, se
        aparearía con la tercera categoría y cambiaría el layout visible.
        """
        cats = [self._Cat(i, f"Cat{i}") for i in range(3)]
        filas = category_selection_options(55, cats)

        assert [len(f) for f in filas] == [2, 1, 1]
        assert filas[-1][0].id == "cat_new:55"

    def test_cantidad_par_de_categorias(self):
        cats = [self._Cat(i, f"Cat{i}") for i in range(4)]
        filas = category_selection_options(55, cats)

        assert [len(f) for f in filas] == [2, 2, 1]
        assert filas[-1][0].id == "cat_new:55"

    def test_sin_categorias_solo_queda_nueva(self):
        filas = category_selection_options(55, [])
        assert [len(f) for f in filas] == [1]
        assert filas[0][0].id == "cat_new:55"