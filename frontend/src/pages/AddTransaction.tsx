import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import styles from './AddTransaction.module.css';

export default function AddTransaction() {
  const navigate = useNavigate();
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('Comida');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // AQUÍ LUEGO LLAMAREMOS A LA API
    console.log("Guardando:", { amount, category });
    
    // Volver al dashboard
    navigate('/');
  };

  return (
    <form className={styles.container} onSubmit={handleSubmit}>
      {/* Header simple con botón atrás */}
      <div style={{ marginBottom: '30px' }}>
        <button 
          type="button" 
          onClick={() => navigate(-1)} 
          style={{ background: 'none', border: 'none', padding: 0 }}
        >
          <ArrowLeft color="var(--text-primary)" />
        </button>
      </div>

      <h1 style={{ marginBottom: '30px' }}>Nuevo Gasto</h1>

      <div className={styles.inputGroup}>
        <label className={styles.label}>Monto</label>
        <input
          type="number"
          className={styles.amountInput}
          placeholder="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          autoFocus
        />
      </div>

      <div className={styles.inputGroup}>
        <label className={styles.label}>Categoría</label>
        <select 
          className={styles.select}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="Comida">🍔 Comida</option>
          <option value="Transporte">🚌 Transporte</option>
          <option value="Servicios">💡 Servicios</option>
          <option value="Ocio">🎉 Ocio</option>
        </select>
      </div>

      <button type="submit" className={styles.saveButton}>
        Guardar Gasto
      </button>
    </form>
  );
}