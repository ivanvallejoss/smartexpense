import { useState, useEffect } from 'react';
import type { Expense, UserBalance } from '../types';
import { ExpenseService } from '../services/api';

export function useDashboardData() {
    const [ expenses, setExpenses ] = useState<Expense[]>([]);
    const [ balance, setBalance ] = useState<UserBalance | null>(null);
    const [ loading, setLoading ] = useState(true);
    const [ error, setError ] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                // Hacemos las dos peticiones en paralelo para ganar tiempo
                const [txData, balanceData] = await Promise.all([
                    ExpenseService.getAll(),
                    ExpenseService.getBalance()
                ]);
                setExpenses(txData);
                setBalance(balanceData);
            } catch(err){
                setError('Error al cargar los datos');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []); // El array vacio significa: "Ejecutar solo al montar el componente"
    return { expenses, balance, loading, error };
}