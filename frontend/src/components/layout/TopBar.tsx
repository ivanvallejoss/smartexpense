import { Bell } from 'lucide-react';
import styles from './TopBar.module.css';

export default function TopBar() {
  // En un futuro, estos datos vendrán de un contexto o de tu hook de usuario
  const userName = "Ivan Vallejos"; 
  
  // Truco Pro: Usamos un servicio gratuito para generar un avatar con las iniciales
  // hasta que implementes la subida de fotos de perfil.
  const avatarUrl = `https://ui-avatars.com/api/?name=Alex+Morgan&background=13e1ec&color=fff&bold=true`;

  return (
    <header className={styles.header}>
      
      <div className={styles.userInfo}>
        <img 
          src={avatarUrl} 
          alt="Avatar del usuario" 
          className={styles.avatar} 
        />
        <div className={styles.greeting}>
          <span className={styles.welcomeText}>Bienvenido!</span>
          <span className={styles.userName}>{userName}</span>
        </div>
      </div>

      <button className={styles.notificationBtn} aria-label="Notificaciones">
        <Bell size={20} />
        {/* El puntito rojo de notificación */}
        <span className={styles.badge}></span>
      </button>

    </header>
  );
}