import { HelpCircle, ShoppingBag, Trash2 } from 'lucide-react'; // Icono genérico por ahora
import type { Expense } from '../../types';
import styles from './ExpenseItem.module.css';

interface ExpenseItemProps extends Expense{
  onDelete?: (id: number) => void
}

export default function ExpenseItem({ id, description, amount, category, date, onDelete }: ExpenseItemProps) {
  
  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);

  const displayCategory = category || {name: 'Sin categoria',color: '#9CA3AF'};
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

      {/* Contenedor derecho para monto y boton */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span className={styles.amount}>-{formattedAmount}</span>
        {/* Si tenemos la funcion onDelete */}
        {onDelete && (
          <button onClick={() => onDelete(id)}
          style={{
            background: 'none', border: 'none', padding: '4px',
            cursor: 'pointer', color: '#ef4444', display: 'flex'
          }}
          title="Eliminar Gasto"
          >
            <Trash2 size={18} /> 
          </button>
        )}
      </div>

      {/* <span className={styles.amount}>-{formattedAmount}</span> */}
    </div>
  );
}