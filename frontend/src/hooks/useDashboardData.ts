import { useState, useEffect, useCallback } from 'react';
import type { Expense, UserBalance } from '../types';
import { ExpenseService } from '../services/api';

const LIMIT = 15;

export function useDashboardData() {
    const [expenses, setExpenses] = useState<Expense[]>([]);
    
    // 1. BALANCE HARDCODEADO (Simple y directo hasta que tengamos el endpoint)
    const [balance, setBalance] = useState<UserBalance | null>({
        totalSpent: 150000, // Valor fijo de prueba
        currency: 'ARS',
        trend: 0
    });
    
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // PAGINACIÓN
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);


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
        if (!expenseToDelete) return;

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

    // 6. EXPORTAMOS TODO LO NECESARIO
    // Agregamos hasMore, loadingMore y loadMore para que el Dashboard pueda usarlos
    return { expenses, balance, loading, error, hasMore, loadingMore, loadMore, deleteExpense };
}