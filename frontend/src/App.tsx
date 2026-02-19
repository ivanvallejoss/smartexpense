import { Routes, Route} from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import History from './pages/History';
import MainLayout from './components/layout/MainLayout';
import AddExpense from './pages/AddExpense';

function App() {
  return (
    <Routes>
      {/* Rutas publicas (sin layout, pantalla completa) */}
      <Route path="/login" element={<Login />} />

      {/* Sin Layout */}
      <Route path="/add" element={<AddExpense />} />

      {/* Tuas privadas (con BottomNav) */}
      <Route element={< MainLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/history" element={<History />} />
        {/* PlaceHolder para el perfil del usuario */}
        <Route path="/profile" element={<h2>Perfile de Usuario</h2>} />
      </Route>

      {/* 404 */}
      <Route path="*" element={<h2>404 = No encontrado</h2>} />
    </Routes>

  );
}

export default App;