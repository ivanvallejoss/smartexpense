import type { Expense, Category} from "../types";
import { getHeaders, handleResponse } from "./api_helpers";


const API_URL = import.meta.env.VITE_API_URL;
const EXPENSE_URL = `${API_URL}/expenses`


export const ExpenseService = {

  // GET
  getAll: async (limit: number=15, offset: number=0): Promise<Expense[]> => {
    
    const response = await fetch(`${EXPENSE_URL}/?limit=${limit}&offset=${offset}`, {
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

    const response = await fetch(`${EXPENSE_URL}/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });

    return handleResponse(response);
  },



  // DELETE
  delete: async (id: number): Promise<void> => {

    const response = await fetch(`${EXPENSE_URL}/${id}/`, {
      method: 'DELETE',
      headers: getHeaders(),
    });

    handleResponse(response)
  },



  // PUT
  update: async (id: number, amount: number, description: string, category_id: number): Promise <Expense> => {

    const response = await fetch(`${EXPENSE_URL}/${id}/`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify({amount, description, category_id})
    });

    return handleResponse(response);
  }
};