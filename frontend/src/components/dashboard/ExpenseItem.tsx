import { HelpCircle, ShoppingBag } from 'lucide-react'; // Icono genérico por ahora
// import { useNavigate } from 'react-router-dom';

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
  // const navigate = useNavigate();
  const displayDate = formatDate(date);


  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);

  const displayCategory = category || {name: 'Sin categoria',color: '#9CA3AF'};
  const Icon = category ? ShoppingBag : HelpCircle;


  // const handleEdit = () => {
  //   // eslint-disable-next-line @typescript-eslint/no-unused-vars
  //   const { onDelete, ...cleanData} = props;
  //   navigate(`/edit/${id}`, { state: {expenseData: cleanData} });
  // }


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
          {/* <span className={styles.category}>{displayCategory.name} • {displayDate}</span> */}
        </div>
      </div>

      {/* RIGHT SIDE: amount + botones */}
      <div className={styles.rightSide}>
        <div className={styles.priceBlock}>
          <span className={styles.amount}>-{formattedAmount}</span>
          <span className={styles.date}>{displayDate}</span>
        </div>

        {/* EDIT
        <button
        onClick={handleEdit}
        className={`${styles.actionBtn} ${styles.editBtn}`}
        title='Editar'
        >
          <Edit2 size={18} />
        </button>

        {/* DELETE*/}
        {/* {onDelete && (
          <button onClick={() => onDelete(id)}
          className={`${styles.actionBtn} ${styles.deleteBtn}`}
          title="Eliminar"
          >
            <Trash2 size={16} /> 
          </button>
        )}  */}
      </div>
    </div>
  );
}