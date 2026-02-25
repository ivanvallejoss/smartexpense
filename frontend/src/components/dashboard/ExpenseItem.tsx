import { HelpCircle, ShoppingBag, Trash2, Edit2 } from 'lucide-react'; // Icono genérico por ahora
import { useNavigate } from 'react-router-dom';

import type { Expense } from '../../types';
import styles from './ExpenseItem.module.css';

interface ExpenseItemProps extends Expense{
  onDelete?: (id: number) => void
}

export default function ExpenseItem(props: ExpenseItemProps) {

  const { id, description, amount, category, date, onDelete} = props;
  const navigate = useNavigate();


  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);

  const displayCategory = category || {name: 'Sin categoria',color: '#9CA3AF'};
  const Icon = category ? ShoppingBag : HelpCircle;


  const handleEdit = () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { onDelete, ...cleanData} = props;
    navigate(`/edit/${id}`, { state: {expenseData: cleanData} });
  }


    return (
    <div className={styles.card}>
      {/* LEFT SIDE */}
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

      {/* RIGHT SIDE: amount + botones */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span className={styles.amount}>-{formattedAmount}</span>
        {/* EDIT */}
        <button
        onClick={handleEdit}
        style={{ background: 'none', border: 'none', padding: '4px', cursor: 'pointer', color: '#3B82F6', display: 'flex' }}
        >
          <Edit2 size={18} />
        </button>

        {/* DELETE*/}
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
    </div>
  );
}