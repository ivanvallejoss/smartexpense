
export interface Transaction {
    id: number;
    merchant: string;
    amount: number;
    category: string;
    date: string;
    // status: 'pending' | 'completed; -> Como podemos escalar esta interface
}

export interface UserBalance {
    total: number;
    currency: string;
    trend: number; // Porcentaje de cambio (ej: 12 para +12%)
}