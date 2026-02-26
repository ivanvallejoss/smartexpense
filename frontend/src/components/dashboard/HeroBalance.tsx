import type { UserBalance } from '../../types';
import styles from './HeroBalance.module.css';

// Definimos los tipos de datos que acepta este componente (TypeScript)
interface HeroBalanceProps {
  balance: UserBalance;
}

export default function HeroBalance({ balance }: HeroBalanceProps) {

  const formattedTotal = new Intl.NumberFormat('es-AR', {
    maximumFractionDigits: 2,
  }).format(balance.totalSpent);

  return (
    <div className={styles.container}>
      <div className={styles.amountContainer}>
        <span className={styles.label}>Total Gastado</span>

        <h1 className={styles.amount}>
          <span className={styles.currency}>$</span>
          {formattedTotal}
        </h1>
      </div>
      <div className={styles.trendContainer}>
        <span className={styles.trendBadge}>
          {/* PROXIMAMENTE: hacer que el icono cambie segun el tren */}
          <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>
            trend
          </span>
          ~12%
        </span>
        <span className={styles.trendText}> vs. mes anterior</span>
      </div>
    </div>
  );
}