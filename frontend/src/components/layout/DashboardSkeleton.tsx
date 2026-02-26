import styles from './Skeleton.module.css';

export default function DashboardSkeleton() {
  return (
    <div style={{ paddingBottom: '80px' }}>
      
      {/* 1. Hero Falso */}
      <div style={{ textAlign: 'center', margin: '2rem 0' }}>
        <div className={`${styles.skeleton} ${styles.heroTitle}`}></div>
        <div className={`${styles.skeleton} ${styles.heroAmount}`}></div>
        <div className={`${styles.skeleton} ${styles.heroBadge}`}></div>
      </div>

      {/* 2. Filtros Falsos */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', overflow: 'hidden' }}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} className={`${styles.skeleton} ${styles.pill}`}></div>
        ))}
      </div>

      {/* 3. Gastos Falsos (Repetimos 5 tarjetas) */}
      <div>
        <h2 style={{ marginBottom: '16px' }}>Últimos Gastos</h2>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className={styles.card}>
            <div className={`${styles.skeleton} ${styles.cardIcon}`}></div>
            
            <div className={styles.cardDetails}>
              <div className={`${styles.skeleton} ${styles.cardLineLong}`}></div>
              <div className={`${styles.skeleton} ${styles.cardLineShort}`}></div>
            </div>
            
            <div className={styles.cardRight}>
              <div className={`${styles.skeleton} ${styles.cardLineLong}`} style={{ width: '100%' }}></div>
              <div className={`${styles.skeleton} ${styles.cardLineShort}`}></div>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}