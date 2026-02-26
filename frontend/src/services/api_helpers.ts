//
// HEADERS helper
//
export const getHeaders = () => {
  const token = localStorage.getItem('jwt_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};


//
// SNAKE_CASE to CAMELCASE helper
//

const toCamelCase = (str: string) => {
  return str.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
};

const keysToCamelCase = (obj: unknown): unknown => {
  // Si es null o no es un objeto (ej. un número o string), lo devolvemos tal cual
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  // Si es un Array, iteramos sobre cada elemento
  if (Array.isArray(obj)) {
    return obj.map(item => keysToCamelCase(item));
  }

  // Si es un Objeto, creamos uno nuevo con las llaves convertidas
  const camelObj: Record<string, unknown> = {};
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      const camelKey = toCamelCase(key);
      // Llamada recursiva por si hay objetos dentro de objetos
      camelObj[camelKey] = keysToCamelCase(obj[key]); 
    }
  }
  return camelObj;
};

// 3. Tu handleResponse mejorado
export const handleResponse = async (response: Response) => {
  if (response.status === 401) {
    localStorage.removeItem('jwt_token');
    window.location.href = '/login'; 
    throw new Error('session expired or invalid');
  }
  
  if (!response.ok) {
    throw new Error(`Error en la API: ${response.statusText}`);
  }
  
  // Si el backend responde un 204 No Content (ej. al hacer DELETE), no hay JSON que parsear
  if (response.status === 204) return null;

  const data = await response.json();
  
  // ✨ LA MAGIA: Traducimos todo antes de dárselo a tus servicios
  return keysToCamelCase(data); 
};