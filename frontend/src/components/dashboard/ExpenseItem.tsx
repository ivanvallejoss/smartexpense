import { HelpCircle, ShoppingBag } from 'lucide-react';

import { formatDate } from '../../utils/formatters';
import type { Expense } from '../../types';
import styles from './ExpenseItem.module.css';

interface ExpenseItemProps extends Expense{
  onDelete?: (id: number) => void
}

export default function ExpenseItem(props: ExpenseItemProps) {

  const { 
    // id, 
    description, 
    amount, 
    category, 
    date, 
    // onDelete
  } = props;
  const displayDate = formatDate(date);


  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);

  const displayCategory = category || {name: 'Sin categoria',color: '#9CA3AF'};
  const Icon = category ? ShoppingBag : HelpCircle;


    return (
    <div className={styles.card}>
      {/* LEFT SIDE */}
      <div className={styles.leftSide}>
        <div 
        className={styles.iconContainer}
        style={{ backgroundColor: `${displayCategory.color}20`, color: displayCategory.color }}
        >
          <Icon size={20} strokeWidth={2.5} />
        </div>
        <div className={styles.details}>
          <span className={styles.merchant}>{description}</span>
          <span className={styles.date}> {displayDate} </span>
        </div>
      </div>

      {/* RIGHT SIDE: amount + botones */}
      <div className={styles.rightSide}>
        <div className={styles.priceBlock}>
          <span className={styles.amount}>-{formattedAmount}</span>
          <span className={styles.category}>{displayCategory.name}</span>
        </div>
      </div>
    </div>
  );
}