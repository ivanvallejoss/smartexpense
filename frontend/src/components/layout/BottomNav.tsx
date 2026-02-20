import { NavLink } from 'react-router-dom';
import { LayoutDashboard, History, User } from 'lucide-react';
import styles from './BottomNav.module.css';

export default function BottomNav() {
  return (
    <nav className={styles.nav}>
      {/* NavLink nos dice si está activo automáticamente */}
      <NavLink 
        to="/" 
        className={({ isActive }) => 
          isActive ? `${styles.link} text-blue-600` : styles.link
        }
        style={({ isActive }) => ({
           color: isActive ? 'var(--primary)' : 'var(--text-secondary)'
        })}
      >
        <LayoutDashboard size={24} />
        <span>Inicio</span>
      </NavLink>

      <NavLink 
        to="/history" 
        className={styles.link}
        style={({ isActive }) => ({
           color: isActive ? 'var(--primary)' : 'var(--text-secondary)'
        })}
      >
        <History size={24} />
        <span>Historial</span>
      </NavLink>

      <NavLink 
        to="/profile" 
        className={styles.link}
        style={({ isActive }) => ({
           color: isActive ? 'var(--primary)' : 'var(--text-secondary)'
        })}
      >
        <User size={24} />
        <span>Perfil</span>
      </NavLink>
    </nav>
  );
}