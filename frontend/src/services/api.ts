import type { Expense, UserBalance, Category } from "../types";

// Datos falsos que simulan venir de la base de datos
let mockExpenses: Expense[] = [
    {id: 1, description: "Supermecado Dia", amount: 15400, category: {id: 4, name: "Comida", color: "#FFF"}, date: "Hoy"},
    {id: 2, description: "Uber", amount: 4200, category: {id: 1, name: "Transporte", color: "#FFF"}, date: "Ayer"},
    {id: 3, description: "Spotify", amount: 599, category: {id: 2, name: "Suscripciones", color: "#FFF"}, date: "20 Feb"},
    {id: 4, description: "Farmacity", amount: 8500, category: {id: 3, name: "Salud", color: "#FFF"}, date: "18 Feb"},
    {id: 5, description: "Netflix", amount: 700, category: {id: 2, name: "Suscripciones", color: "#FFF"}, date: "15 Feb"},
    {id: 6, description: "Sube", amount: 10000, category: {id: 1, name: "Transporte", color: "#FFF"}, date: "14 Feb"},    
];

export const ExpenseService = {
    // Simula un GET /Expense
    getAll: async(): Promise<Expense[]> => {
        return new Promise(resolve => {
            setTimeout(() => {
                // Usamos [...] para devolver una copia y evitar bugs de referencia
                resolve([...mockExpenses]);
            }, 2000); // Tardamos 2 segundos a proposito (para ver el loading)
        })
    },

    // Simula un GET /balance
    getBalance: async(): Promise<UserBalance> => {
        return new Promise(resolve => {
            setTimeout(() => {
                const totalSpent = mockExpenses.reduce((acc, curr) => acc + curr.amount, 0);
                resolve({
                    totalSpent: totalSpent,
                    currency: 'ARS',
                    trend: 12
                });
            }, 1000);
        });
    },

    create: async (amount: number, category: Category, description: string = "Gasto Manual"):
    Promise<Expense> => {
        return new Promise(resolve => {
            setTimeout(() => {
                const newTx: Expense = {
                    id: Date.now(), // Usamos la fecha como id, ESTO ES TEMPORAL 
                    amount: amount,
                    category: category,
                    description: description,
                    date: "Ahora mismo"
                };

                mockExpenses.unshift(newTx);
                resolve(newTx);
            }, 1000); // Simulamos que el servidor tarda 1s en guardar
        }) 
    }
};
