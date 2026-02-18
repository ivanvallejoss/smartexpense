import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import styles from './AddTransaction.module.css';
import { TransactionService } from '../services/api';


export default function AddTransaction() {
  const navigate = useNavigate();
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('Comida');
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validacion basica
    if (!amount || isNaN(Number(amount))) return;

    try{
      setIsSaving(true); // Bloqueamos el boton
      // 2. Llamamos al servicio para simular la peticion al backend
      await TransactionService.create(Number(amount), category);

      // 3. Volvemos al dashboard
      navigate('/')
    } catch(error) {
      console.error("Error al guardar", error);
      alert("Hubo un error al guardar el gasto");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form className={styles.container} onSubmit={handleSubmit}>
      {/* Header simple con botón atrás */}
      <div style={{ marginBottom: '30px' }}>
        <button 
          type="button" 
          onClick={() => navigate(-1)} 
          style={{ background: 'none', border: 'none', padding: 0 , cursor: 'pointer'}}
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

      <button type="submit" 
      className={styles.saveButton}
      disabled={isSaving}
      style={{ opacity: isSaving ? 0.7: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px' }}
      >
        {isSaving ? (
          <>
          <Loader2 className='animate-spin' /> Guardando...
          </>
        ) : (
          'Guardar Gasto'
        )}
      </button>
    </form>
  );
}