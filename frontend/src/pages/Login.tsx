// src/pages/Login.tsx
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  // Este hook de React Router lee los parámetros de la URL (?token=...)
  const [searchParams] = useSearchParams(); 

  useEffect(() => {
    // 1. Extraemos el token de la URL: http://tusitio.com/login?token=eyJhbG...
    const token = searchParams.get('token');

    if (token) {
      // 2. Lo guardamos (LocalStorage es el estándar para SPAs por ahora)
      localStorage.setItem('jwt_token', token);

      // 3. Limpiamos la URL y redirigimos al Dashboard.
      // El { replace: true } es MAGIA: borra el /login?token=... del historial del navegador.
      // Así, si el usuario presiona "Atrás" en el celular, no vuelve a la URL con el token,
      // sino que se sale de la app. ¡Pura seguridad!
      navigate('/', { replace: true });
    }
  }, [searchParams, navigate]);

  // Si no hay token, mostramos las instrucciones
  if (!searchParams.get('token')) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', marginTop: '50vh', transform: 'translateY(-50%)' }}>
        <h1>🔐 SmartExpense</h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '10px' }}>
          Para ingresar, solicita tu Magic Link a nuestro bot de Telegram usando el comando <b>/link</b>.
        </p>
      </div>
    );
  }

  // Si hay token, mostramos un spinner mientras procesa la redirección (dura milisegundos)
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Loader2 className="animate-spin" size={48} color="var(--primary)" />
      <span style={{ marginLeft: '10px' }}>Autenticando...</span>
    </div>
  );
}