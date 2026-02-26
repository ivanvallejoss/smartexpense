import { HelpCircle, ShoppingBag, Check, X, Trash2 } from 'lucide-react';

import { formatDate } from '../../utils/formatters';
import type { Expense } from '../../types';
import styles from './ExpenseItem.module.css';
import { useState } from 'react';

interface ExpenseItemProps extends Expense{
  onDelete?: (id: number) => void;
  onUpdate?: (id: number, amount: number, description: string, category_id: number) => Promise<void>;
}

// MOCK temporal para el select
const CATEGORIES = [
  {id: 1, name: 'Comida'}, {id: 2, name: 'Transporte'}, {id: 3, name: 'Servicio'}
];


export default function ExpenseItem(props: ExpenseItemProps) {

  const { id, description, amount, category, date, onDelete, onUpdate} = props;

  // ESTADOS para el modo edicion
  const [isEditing, setIsEditing] = useState(false);
  const [editDesc, setEditDesc] = useState(description);
  const [editAmount, setEditAmount] = useState(amount.toString());
  const [editCatId, setEditCatId] = useState(category?.id || 1);
  const [isSaving, setIsSaving] = useState(false);


  // FORMATEADORES
  const formattedAmount = new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    maximumFractionDigits: 0
  }).format(amount);
  const displayDate = formatDate(date);
  const displayCategory = category || {name: 'Sin categoria',color: '#9CA3AF'};
  const Icon = category ? ShoppingBag : HelpCircle;


  // HANDLERS
  const handleSave = async(e: React.MouseEvent) => {
    e.stopPropagation(); // Evita que el click cierre la tarjeta

    if (!onUpdate || !editDesc || !editAmount) return;
    
    try {
      setIsSaving(true);
      await onUpdate(id, Number(editAmount), editDesc, Number(editCatId));
      setIsEditing(false);
    } catch (err){
      alert(`Error al guardar: ${err}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete) onDelete(id);
  };

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Reseteamos los valores a como estaban en la BD
    setEditDesc(description);
    setEditAmount(amount.toString());
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <div className={`${styles.card} ${styles.cardEditing}`}>
        
        <div className={styles.editRow}>
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, marginRight: '1rem' }}>
            <input 
              type="text" 
              className={`${styles.inlineInput} ${styles.inputDesc}`} 
              value={editDesc} 
              onChange={e => setEditDesc(e.target.value)} 
              autoFocus 
            />
            <select 
              className={styles.categorySelect}
              value={editCatId}
              onChange={e => setEditCatId(Number(e.target.value))}
            >
              {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ fontWeight: 'bold', color: 'var(--color-danger)' }}>$</span>
            <input 
              type="number" 
              className={`${styles.inlineInput} ${styles.inputAmount}`} 
              value={editAmount} 
              onChange={e => setEditAmount(e.target.value)} 
            />
          </div>
        </div>

        <div className={styles.editActions}>
          <button className={`${styles.btnInline} ${styles.btnDelete}`} onClick={handleDelete}>
            <Trash2 size={14} />
          </button>
          <button className={`${styles.btnInline} ${styles.btnCancel}`} onClick={handleCancel}>
            <X size={14} /> Cancelar
          </button>
          <button className={`${styles.btnInline} ${styles.btnSave}`} onClick={handleSave} disabled={isSaving}>
            <Check size={14} /> {isSaving ? '...' : 'Guardar'}
          </button>
        </div>
      </div>
    );
  }

    return (
    <div className={styles.card} onClick={() => setIsEditing(true)} style={{ cursor: 'pointer' }}>
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