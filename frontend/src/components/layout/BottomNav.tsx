import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Home, PieChart, Plus, CreditCard, User } from 'lucide-react';
import styles from './BottomNav.module.css';

export default function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  // Función auxiliar para saber si un tab está activo
  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className={styles.nav}>
      <div className={styles.container}>
        
        {/* Tab: Home */}
        <Link to="/" className={`${styles.navItem} ${isActive('/') ? styles.active : ''}`}>
          <div className={styles.iconWrapper}>
            <Home size={24} strokeWidth={isActive('/') ? 2.5 : 2} />
          </div>
          <span className={styles.label}>Inicio</span>
        </Link>

        {/* Tab: Stats (History) */}
        <Link to="/history" className={`${styles.navItem} ${isActive('/history') ? styles.active : ''}`}>
          <div className={styles.iconWrapper}>
            <PieChart size={24} strokeWidth={isActive('/history') ? 2.5 : 2} />
          </div>
          <span className={styles.label}>Stats</span>
        </Link>

        {/* FAB: Agregar Gasto */}
        <div className={styles.fabContainer}>
          <button 
            className={styles.fab} 
            onClick={() => navigate('/add')}
            aria-label="Agregar Gasto"
          >
            <Plus size={32} strokeWidth={3} />
          </button>
        </div>

        {/* Tab: Cards (Placeholder) */}
        <Link to="#" className={styles.navItem}>
          <div className={styles.iconWrapper}>
            <CreditCard size={24} />
          </div>
          <span className={styles.label}>Tarjetas</span>
        </Link>

        {/* Tab: Profile (Placeholder) */}
        <Link to="/profile" className={`${styles.navItem} ${isActive('/profile') ? styles.active : ''}`}>
          <div className={styles.iconWrapper}>
            <User size={24} strokeWidth={isActive('/profile') ? 2.5 : 2} />
          </div>
          <span className={styles.label}>Perfil</span>
        </Link>

      </div>
    </nav>
  );
}