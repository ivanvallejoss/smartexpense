import type { Expense, Category, UserBalance} from "../types";
import { getHeaders, handleResponse } from "./api_helpers";


const API_URL = import.meta.env.VITE_API_URL;
const EXPENSE_URL = `${API_URL}/expenses`
const BALANCE_URL = `${API_URL}/balances`


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
  },

};



export const BalanceService = {
  
  // GET
  get: async(month?: number, year?: number): Promise <UserBalance> => {
    const params = new URLSearchParams();

    if (month) params.append('month', month.toString());
    if (year) params.append('year', year.toString());

    const queryString = params.toString();
    const urlBalance = queryString ? `${BALANCE_URL}/?${queryString}`: `${BALANCE_URL}/`;
    
    const response = await fetch(urlBalance, {
      method: 'GET',
      headers: getHeaders()
    });

    return handleResponse(response);
  },

} ;