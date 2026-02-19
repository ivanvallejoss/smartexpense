import HeroBalance from "../components/dashboard/HeroBalance";
import ExpenseItem from "../components/dashboard/ExpenseItem";
import FloatingActionButton from "../components/ui/FloatingActionButton";
import { useDashboardData } from "../hooks/useDashboardData";

export default function Dashboard(){
    // Usamos el hook.
    const { expenses, balance, loading, error } = useDashboardData();

    if (loading) {
        return (
            <div style={{ padding: '20px', textAlign: 'center', marginTop: '50px' }}>
                <p>Cargando tus finanzas..</p>
                {/* Aqui luego ira un skeleton Loader */}
            </div>
        );
    }
    if (error) {
        return <div style={{ color: 'red', padding: '20px' }}>ERROR: {error}</div>
    }

    return (
        <div style={{ padding: '20px', maxWidth: '480px', margin: '0 auto' }}>
            <header style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '1.2rem', color: 'var(--text-secondary)'}}>Hola, Usuario</h1>
            </header>   

            <HeroBalance total={balance?.totalSpent || 0}/>
            
            <h3 style={{ margin: '20px 0 10px', fontSize: '1.1rem', fontWeight: 600 }}>
                Movimientos Recientes
            </h3>

            <div className="list-container">
                {expenses.map(tx => (
                    <ExpenseItem
                    key={tx.id}
                    description={tx.description}
                    amount={tx.amount}
                    category={tx.category}
                    date={tx.date}
                    />
                ))}
            </div>
            <FloatingActionButton />
        </div>
    );
}