import HeroBalance from "../components/dashboard/HeroBalance";
import TransactionItem from "../components/dashboard/TransactionItem";
import { useDashboardData } from "../hooks/useDashboardData";

// Datos de prueba (Luego vendran de la API de Django)
const MOCK_TRANSACTION = [
    {id: 1, merchant: "Supermecado Dia", amount: 15400, category: "Comida", date: "Hoy"},
    {id: 2, merchant: "Uber", amount: 4200, category: "Transporte", date: "Ayer"},
    {id: 3, merchant: "Spotify", amount: 599, category: "Suscripciones", date: "20 Feb"},
];


export default function Dashboard(){
    // Usamos el hook.
    const { transactions, balance, loading, error } = useDashboardData();

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

            <HeroBalance total={balance?.total || 0}/>
            
            <h3 style={{ margin: '20px 0 10px', fontSize: '1.1rem', fontWeight: 600 }}>
                Movimientos Recientes
            </h3>

            <div className="list-container">
                {transactions.map(tx => (
                    <TransactionItem
                    key={tx.id}
                    merchant={tx.merchant}
                    amount={tx.amount}
                    category={tx.category}
                    date={tx.date}
                    />
                ))}
            </div>

        </div>
    );
}