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

                const expensesData = await ExpenseService.getAll();

                // 2. CÁLCULO MANUAL (Mitigación en Frontend)
                // Sumamos todos los montos del array que nos devolvió el backend
                const totalCalculado = expensesData.reduce((acumulador, gasto) => {
                    return acumulador + gasto.amount;
                }, 0);

                // Devolvemos las expensas
                setExpenses(expensesData);
                
                // Seteamos manualmente el objeto que espera recibir el balance
                setBalance({
                    totalSpent: totalCalculado,
                    currency: 'ARS',
                    trend: 0 // Dato mockeado temporalmente
                });
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
