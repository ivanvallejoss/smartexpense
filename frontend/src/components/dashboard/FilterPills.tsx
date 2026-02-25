import { useState } from 'react';
import styles from './FilterPills.module.css';

// Mock de categorías. En el futuro, esto podría venir como Props desde el backend.
const MOCK_CATEGORIES = [
  { id: 'all', name: 'Todos' },
  { id: 'food', name: 'Comida' },
  { id: 'transport', name: 'Transporte' },
  { id: 'shopping', name: 'Compras' },
  { id: 'bills', name: 'Servicios' },
];

export default function FilterPills() {
  // Lógica de UI aislada (solo afecta a los colores de estos botones)
  const [activeFilter, setActiveFilter] = useState('all');

  return (
    <div className={styles.scrollContainer}>
      {MOCK_CATEGORIES.map((category) => (
        <button
          key={category.id}
          onClick={() => setActiveFilter(category.id)}
          className={`${styles.pill} ${activeFilter === category.id ? styles.pillActive : ''}`}
        >
          {category.name}
        </button>
      ))}
    </div>
  );
}