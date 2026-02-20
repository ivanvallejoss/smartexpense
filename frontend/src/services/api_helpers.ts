`
Funciones helpers para services/api
`


export const getHeaders = () => {
  const token = localStorage.getItem('jwt_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};


export const handleResponse = async (response: Response) => {
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