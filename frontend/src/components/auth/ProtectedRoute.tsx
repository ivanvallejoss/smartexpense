import { Navigate, Outlet } from 'react-router-dom';

export default function ProtectedRoute(){
    const token = localStorage.getItem('jwt_token');

    // Si no hay token en el navegado, lo pateamos al login
    // El 'replace' borra el intento fallido del historial del navegador
    if(!token){
        return <Navigate to="/login" replace/>
    }

    // Si hay token, <Outlet/> le dice a React Router: "Deja pasar al componente hijo"
    return <Outlet />
}