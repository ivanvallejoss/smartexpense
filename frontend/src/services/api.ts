import type { Expense, Category} from "../types";
import { getHeaders, handleResponse } from "./api_helpers";


const API_URL = import.meta.env.VITE_API_URL;
const EXPENSE_URL = `${API_URL}/expenses/`


export const ExpenseService = {
  // GET
  getAll: async (): Promise<Expense[]> => {
    const response = await fetch(EXPENSE_URL, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  // POST:
  create: async (amount: number, description: string, category: Category): Promise<Expense> => {
    const payload = {
      amount: amount,
      description: description,
      category_id: category.id
    };

    const response = await fetch(EXPENSE_URL, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  // GET: Obtener balance
  // Todavia no cree este endpoint, queda para despues

  // getBalance: async (): Promise<UserBalance> => {
  //   const response = await fetch(`${API_URL}/balance`, {
  //     method: 'GET',
  //     headers: getHeaders(),
  //   });
  //   return handleResponse(response);
  // }
};