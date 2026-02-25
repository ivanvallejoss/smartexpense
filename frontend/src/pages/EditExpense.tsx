import { useState } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { ExpenseService } from '../services/api';
import styles from './AddExpense.module.css';

const AVAILABLE_CATEGORIES = [
    {id: 1, name: "Comida"}, {id: 2, name: "Transporte"}, {id: 3, name: "Servicios"}, {id: 4, name: "Ocio"}, {id: 5, name: "Supermercado"}, {id: 6, name: "Suscripciones"} 
];


export default function EditExpense() {
    const navigate = useNavigate();
    const location = useLocation();
    const { id } = useParams(); // Sacamos el ID de la URL

    // Recuperamos los datos que mandamos desde el expenseItem
    const expenseToEdit = location.state?.expenseData;

    // Inicilizamos los estados con los datos existentes.
    // Si alguien entra directo a la URL sin pasar por el boton, expenseToEdit sera undefined
    // por lo que podria redirigirlo al dashboard o hacer un fetch manual
    const [amount, setAmount] = useState(expenseToEdit?.amount || '');
    const [description, setDescription] = useState(expenseToEdit?.description || '');
    const [selectedCategoryId, setSelectedCategoryId] = useState(expenseToEdit?.category?.id || AVAILABLE_CATEGORIES[0].id)
    const [isSaving, setIsSaving] = useState(false);

    const handleSubmit = async (e: React.SubmitEvent) => {
        e.preventDefault();
        if (!amount || isNaN(Number(amount)) || !description) return;

        try {
            setIsSaving(true);
            // Llamamos al put enviando el ID de la URL
            await ExpenseService.update(Number(id), Number(amount), description, Number(selectedCategoryId));
            navigate('/', {replace: true}); // Volvemos al dashboard
        } catch(err) {
            console.error("Error al actualizar", err); 
            alert("Hubo un error al actualizar el gasto");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <form className={styles.container} onSubmit={handleSubmit}>
        {/* Header simple con botón atrás */}
        <div style={{ marginBottom: '30px', display:'flex', alignItems: 'center'}}>
            <button 
            type="button" 
            onClick={() => navigate(-1)} 
            style={{ background: 'none', border: 'none', padding: 0 , cursor: 'pointer'}}
            >
            <ArrowLeft color="var(--text-primary)" />
            </button>
            <h2 style={{ font: '1em', padding: '0 0 0 10%' }}>Actualizacion de Gasto</h2>
        </div>


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
            onChange={(e) => setSelectedCategoryId(Number(e.target.value))}
            >
            {AVAILABLE_CATEGORIES.map(cat => (
                <option key={cat.id} value={cat.id}>
                {cat.name}
                </option>
            ))}
            </select>
        </div>
            <button type="submit" className={styles.saveButton} disabled={isSaving}
            style={{ opacity: isSaving ? 0.7: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px' }}
            >
                {isSaving ? ( 
                    <>
                    <Loader2 className="animate-spin" /> Actualizando.. 
                    </> 
                ) : ( 
                    'Actualizar Gasto'
                )}
            </button>
    </form>
    )


}