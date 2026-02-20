import styles from './HeroBalance.module.css';

// Definimos los tipos de datos que acepta este componente (TypeScript)
interface HeroBalanceProps {
  total: number;
  label?: string; // El signo ? significa que es opcional
}

export default function HeroBalance({ total, label = "Gastado esta semana" }: HeroBalanceProps) {
  // Formateador de moneda (para que ponga el $)
  const formattedTotal = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(total);

  return (
    <div className={styles.container}>
      <div className={styles.label}>{label}</div>
      <h2 className={styles.amount}>{formattedTotal}</h2>
      <span className={styles.trend}>+12% vs semana pasada</span>
    </div>
  );
}