import { ShoppingBag } from 'lucide-react'; // Icono genérico por ahora
import styles from './TransactionItem.module.css';

interface TransactionItemProps {
  merchant: string;
  amount: number;
  category: string;
  date: string;
}

export default function TransactionItem({ merchant, amount, category, date }: TransactionItemProps) {
    const formattedAmount = new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS',
        maximumFractionDigits: 0
      }).format(amount);

  return (
    <div className={styles.card}>
      <div className={styles.left}>
        <div className={styles.icon}>
          <ShoppingBag size={20} />
        </div>
        <div className={styles.details}>
          <span className={styles.merchant}>{merchant}</span>
          <span className={styles.category}>{category} • {date}</span>
        </div>
      </div>
      <span className={styles.amount}>-{formattedAmount}</span>
    </div>
  );
}