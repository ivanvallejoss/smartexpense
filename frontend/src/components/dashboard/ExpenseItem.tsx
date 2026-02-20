import { ShoppingBag } from 'lucide-react'; // Icono genérico por ahora
import type { Expense } from '../../types';
import styles from './ExpenseItem.module.css';

interface ExpenseItemProps extends Omit<Expense, 'id'> {}

export default function ExpenseItem({description, amount, category, date}: ExpenseItemProps) {
  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);

    return (
    <div className={styles.card}>
      <div className={styles.left}>
        <div 
        className={styles.icon}
        style={{ backgroundColor: category.color + '20', color: category.color }}
        >
          <ShoppingBag size={20} />
        </div>
        <div className={styles.details}>
          <span className={styles.merchant}>{description}</span>
          <span className={styles.category}>{category.name} • {date}</span>
        </div>
      </div>
      <span className={styles.amount}>-{formattedAmount}</span>
    </div>
  );
}