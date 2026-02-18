import type { Transaction, UserBalance } from "../types";

// Datos falsos que simulan venir de la base de datos
let mockTransactions: Transaction[] = [
    {id: 1, merchant: "Supermecado Dia", amount: 15400, category: "Comida", date: "Hoy"},
    {id: 2, merchant: "Uber", amount: 4200, category: "Transporte", date: "Ayer"},
    {id: 3, merchant: "Spotify", amount: 599, category: "Suscripciones", date: "20 Feb"},
    {id: 4, merchant: "Farmacity", amount: 8500, category: "Salud", date: "18 Feb"},
    {id: 5, merchant: "Netflix", amount: 700, category: "Suscripciones", date: "15 Feb"},
    {id: 4, merchant: "Sube", amount: 10000, category: "Transporte", date: "14 Feb"},    
];

export const TransactionService = {
    // Simula un GET /transaction
    getAll: async(): Promise<Transaction[]> => {
        return new Promise(resolve => {
            setTimeout(() => {
                // Usamos [...] para devolver una copia y evitar bugs de referencia
                resolve([...mockTransactions]);
            }, 2000); // Tardamos 2 segundos a proposito (para ver el loading)
        })
    },

    // Simula un GET /balance
    getBalance: async(): Promise<UserBalance> => {
        return new Promise(resolve => {
            setTimeout(() => {
                const total = mockTransactions.reduce((acc, curr) => acc + curr.amount, 0);
                resolve({
                    total: total,
                    currency: 'ARS',
                    trend: 12
                });
            }, 1000);
        });
    },

    create: async (amount: number, category: string, merchant: string = "Gasto Manual"):
    Promise<Transaction> => {
        return new Promise(resolve => {
            setTimeout(() => {
                const newTx: Transaction = {
                    id: Date.now(), // Usamos la fecha como id, ESTO ES TEMPORAL 
                    amount: amount,
                    category: category,
                    merchant: merchant,
                    date: "Ahora mismo"
                };

                mockTransactions.unshift(newTx);
                resolve(newTx);
            }, 1000); // Simulamos que el servidor tarda 1s en guardar
        }) 
    }
};
