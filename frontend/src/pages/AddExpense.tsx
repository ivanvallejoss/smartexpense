import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import styles from './AddExpense.module.css';
import { ExpenseService } from '../services/api';
import type { Category } from '../types';


// Simulamos las categorias
const AVAILABLE_CATEGORIES: Category[] = [
  {id: 1, name: "Comida", color: "#FFF"},
  {id: 2, name: "Transporte", color: "#FEF"},
  {id: 3, name: "Suscripciones", color: "#EFE"},
  {id: 4, name: "Salud", color: "#AFF"}
]


export default function AddExpense() {
  const navigate = useNavigate();
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [selectedCategoryId, setselectedCategoryId] = useState<number>(AVAILABLE_CATEGORIES[0].id);
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (e: React.SubmitEvent) => {
    e.preventDefault();

    // Validacion basica
    if (!amount || isNaN(Number(amount)) || !description) return;

    try{
      setIsSaving(true); // Bloqueamos el boton

      const categoryObject = AVAILABLE_CATEGORIES.find(c => c.id === Number(selectedCategoryId));

      if(!categoryObject){
        throw new Error("Categoria no valida");
      }

      // 2. Llamamos al servicio para simular la peticion al backend
      await ExpenseService.create(Number(amount), description, categoryObject);

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

      {/* MONTO */}
      <div className={styles.inputGroup}>
        <label className={styles.label}>Monto</label>
        <input
          type="number"
          className={styles.amountInput}
          placeholder="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          disabled={isSaving}
        />
      </div>
      {/* DESCRIPTION */}
      <div className={styles.inputGroup}>
        <label className={styles.label}>Description</label>
        <input
          type="text"
          className={styles.select}
          placeholder="Ej: 'Uber al centro'"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isSaving}
        />
      </div>
      {/* CATEGORIA */}
      <div className={styles.inputGroup}>
        <label className={styles.label}>Categoría</label>
        <select 
          className={styles.select}
          value={selectedCategoryId}
          onChange={(e) => setselectedCategoryId(Number(e.target.value))}
        >
          {AVAILABLE_CATEGORIES.map(cat => (
            <option key={cat.id} value={cat.id}>
              {cat.name}
            </option>
          ))}
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