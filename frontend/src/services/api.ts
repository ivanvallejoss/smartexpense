import type { Transaction, UserBalance } from "../types";

// Datos falsos que simulan venir de la base de datos
const MOCK_DATA: Transaction[] = [
    {id: 1, merchant: "Supermecado Dia", amount: 15400, category: "Comida", date: "Hoy"},
    {id: 2, merchant: "Uber", amount: 4200, category: "Transporte", date: "Ayer"},
    {id: 3, merchant: "Spotify", amount: 599, category: "Suscripciones", date: "20 Feb"},
    {id: 4, merchant: "Farmacity", amount: 8500, category: "Salud", date: "18 Feb"},
];

export const TransactionService = {
    // Simula un GET /transaction
    getAll: async(): Promise<Transaction[]> => {
        return new Promise(resolve => {
            setTimeout(() => {
                resolve(MOCK_DATA);
            }, 2000); // Tardamos 1.5 segundos a proposito (para ver el loading)
        })
    },

    // Simula un GET /balance
    getBalance: async(): Promise<UserBalance> => {
        return new Promise(resolve => {
            setTimeout(() => {
                resolve({
                    total: 125600,
                    currency: 'ARS',
                    trend: 12
                });
            }, 1500);
        });
    }
};
