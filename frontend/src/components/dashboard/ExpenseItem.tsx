import { HelpCircle, ShoppingBag } from 'lucide-react'; // Icono genérico por ahora
import type { Expense } from '../../types';
import styles from './ExpenseItem.module.css';

interface ExpenseItemProps extends Omit<Expense, 'id'> {}

export default function ExpenseItem({description, amount, category, date}: ExpenseItemProps) {
  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);

  const displayCategory = category || {
    name: 'Sin categoria',
    color: '#9CA3AF', // Un gris neutro
  };

  const Icon = category ? ShoppingBag : HelpCircle;

    return (
    <div className={styles.card}>
      <div className={styles.left}>
        <div 
        className={styles.icon}
        style={{ backgroundColor: displayCategory.color + '20', color: displayCategory.color }}
        >
          <Icon size={20} />
        </div>
        <div className={styles.details}>
          <span className={styles.merchant}>{description}</span>
          <span className={styles.category}>{displayCategory.name} • {date}</span>
        </div>
      </div>
      <span className={styles.amount}>-{formattedAmount}</span>
    </div>
  );
}