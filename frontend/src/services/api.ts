import type { Expense, Category} from "../types";

// 1. Obtenemos la URL base del entorno
const API_URL = import.meta.env.VITE_API_URL;

// 2. Función Helper: Construye las cabeceras (headers) inyectando el JWT
const getHeaders = () => {
  const token = localStorage.getItem('jwt_token');
  return {
    'Content-Type': 'application/json',
    // Si hay token, lo mandamos en el formato estándar de autorización
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

// 3. Función Helper: Maneja las respuestas y errores comunes
const handleResponse = async (response: Response) => {
  if (response.status === 401) {
    // 401 Unauthorized: El token expiró o es inválido.
    // Borramos la evidencia y pateamos al usuario al login.
    localStorage.removeItem('jwt_token');
    window.location.href = '/login'; 
    throw new Error('Sesión expirada o inválida');
  }
  
  if (!response.ok) {
    throw new Error(`Error en la API: ${response.statusText}`);
  }
  
  return response.json();
};

const url_exacta = `${API_URL}/expenses/`
console.log(`haciendo fetch a: ${url_exacta}`)

export const ExpenseService = {
  // GET: Traer todos los gastos
  getAll: async (): Promise<Expense[]> => {
    const response = await fetch(url_exacta, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  // POST: Crear un nuevo gasto (Respetando tu Schema ExpenseIn)
  create: async (amount: number, description: string, category: Category): Promise<Expense> => {
    // Construimos el payload exactamente como lo pide tu backend
    const payload = {
      amount: amount,
      description: description,
      category_id: category.id // ¡Mandamos solo el ID como acordamos!
    };

    const response = await fetch(`${API_URL}/expenses`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(payload),
    });
    return handleResponse(response);
  },

  // GET: Obtener balance
  // (Si aún no tienes este endpoint, podemos calcularlo sumando el getAll por ahora)
  // getBalance: async (): Promise<UserBalance> => {
  //   const response = await fetch(`${API_URL}/balance`, {
  //     method: 'GET',
  //     headers: getHeaders(),
  //   });
  //   return handleResponse(response);
  // }
};