import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import History from './pages/History';

function App() {
  return (
    <div>
      {/* ⚠️ MENU TEMPORAL (Solo para desarrollo) */}
      <nav style={{ padding: '10px', borderBottom: '1px solid #ccc', marginBottom: '20px' }}>
        <Link to="/" style={{ marginRight: '10px' }}>Home</Link> | 
        <Link to="/login" style={{ margin: '0 10px' }}>Login</Link> | 
        <Link to="/history" style={{ marginLeft: '10px' }}>Historial</Link>
      </nav>

      {/* Aquí es donde React renderiza la página activa */}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/login" element={<Login />} />
        <Route path="/history" element={<History />} />
        
        {/* Ruta 404 (Opcional por ahora) */}
        <Route path="*" element={<h2>404 - Página no encontrada</h2>} />
      </Routes>
    </div>
  );
}

export default App;