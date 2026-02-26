import { useState, useEffect, useCallback } from 'react';
import type { Expense, UserBalance } from '../types';
import { ExpenseService, BalanceService } from '../services/api';

const LIMIT = 15;

export function useDashboardData() {
    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [balance, setBalance] = useState<UserBalance | null>(null);
    
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // PAGINACIÓN
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);


    // HERO BALANCE 
    const fetchBalance = async() => {
        try{
            const data = await BalanceService.get();
            setBalance(data);
        } catch (err) {
            console.error("Error obteniendo el balance: ", err);
            // Solo dejamos el balance en null si fall
        }
    }

    // EXPENSES LIST
    const fetchExpense = async (currentOffset: number) => {
        try {
            // Si es la primera carga, spinner principal. Si es scroll, spinner pequeño.
            if  (currentOffset === 0){
                setLoading(true)
            } else { 
                setLoadingMore(true)
            };

            const newExpenses = await ExpenseService.getAll(LIMIT, currentOffset);

            // Si Django manda menos del límite, llegamos al final de la tabla en BD
            if (newExpenses.length < LIMIT) {
                setHasMore(false);
            }

            // Si estamos en la página cero, pisamos la lista. Si no, concatenamos.
            if (currentOffset === 0) {
                setExpenses(newExpenses);
            } else {
                setExpenses(prev => [...prev, ...newExpenses]);
            }
        } catch (err) {
            setError('Error al cargar los datos');
            console.error(err);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    };

    // Se ejecuta al montar el componente (offset es 0) y cada vez que el offset cambia
    useEffect(() => {
        // Si es la primera carga, obtenemos el balance
        if (offset === 0){
            fetchBalance();
        };

        fetchExpense(offset);
    }, [offset]);

    //  EL DISPARADOR DEL SCROLL
    const loadMore = useCallback(() => {
        if (!loading && !loadingMore && hasMore) {
            setOffset(prev => prev + LIMIT);
        }
    }, [loading, loadingMore, hasMore]);

    //  LÓGICA DE BORRADO
    const deleteExpense = async (id: number) => {
        const expenseToDelete = expenses.find(e => e.id === id);
        if (!expenseToDelete){ 
            console.error(`No expenses matched id: ${id}`);
            return;
        }
        try {
            await ExpenseService.delete(id);
            setExpenses(prevExpenses => prevExpenses.filter(e => e.id !== id));
            
            // Opcional: Le restamos al balance hardcodeado para mantener el efecto visual
            setBalance(prev => prev ? {
                ...prev,
                totalSpent: prev.totalSpent - expenseToDelete.amount
            } : null);
        } catch (err) {
            console.error("Error al borrar el gasto: ", err);
            alert("No se pudo eliminar el gasto. Intenta de nuevo");
        }
    };

    const updateExpense = async(id: number, amount: number, description: string, category_id: number) => {
        //  Buscamos el gasto original para saber cuanto costaba antes
        const oldExpense = expenses.find(e => e.id === id);
        if (!oldExpense) return;

        try {
            //  Le pegamos a la API
            // Asumimos que expenseservice.update devuelve el gasto actualizado con su categoria nueva
            const updatedExpense = await ExpenseService.update(id, amount, description, category_id);

            // Actualizamos la lista de gastos visual
            setExpenses(prevExpenses => prevExpenses.map(expense => 
                expense.id === id ? {
                    ...expense,
                    amount,
                    description,
                    category: updatedExpense.category
                } : expense
            ));
            // Si antes era 100 y ahora 1500, la diferencia es +500 al balance
            const difference = amount - oldExpense.amount;

            setBalance(prev => prev ? {
                ...prev,
                totalSpent: prev.totalSpent + difference
            }: null);
        } catch(err) {
            console.error("Error al actualizar el gasto: ", err)
            alert("No se pudo actualizar el gasto. Revisa tu conexion.")
            throw err; // Lanzamos el error para que el expenseItem desactive su spinner
        }

    }

    // 6. EXPORTAMOS TODO LO NECESARIO
    // Agregamos hasMore, loadingMore y loadMore para que el Dashboard pueda usarlos
    return { expenses, balance, loading, error, hasMore, loadingMore, loadMore, deleteExpense, updateExpense };
}