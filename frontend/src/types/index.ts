
export interface Expense {
    id: number;
    description: string;
    amount: number;
    category: Category;
    date: string;
    // status: 'pending' | 'completed; -> Como podemos escalar esta interface
}

export interface UserBalance {
    totalSpent: number;
    currency: string;
    trend?: number; // Porcentaje de cambio (ej: 12 para +12%)
}

export interface Category {
    id: number;
    name: string;
    color: string;
}