import { Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import styles from './FloatingActionButton.module.css';

export default function FloatingActionButton() {
  const navigate = useNavigate();

  return (
    <button 
      className={styles.fab} 
      onClick={() => navigate('/add')}
      aria-label="Agregar Gasto"
    >
      <Plus size={28} strokeWidth={3} />
    </button>
  );
}