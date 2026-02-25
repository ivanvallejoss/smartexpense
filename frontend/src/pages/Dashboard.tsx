import HeroBalance from "../components/dashboard/HeroBalance";
import ExpenseItem from "../components/dashboard/ExpenseItem";
import FloatingActionButton from "../components/ui/FloatingActionButton";
import { useDashboardData } from "../hooks/useDashboardData";
import { useEffect, useRef } from "react";


export default function Dashboard(){
    
    // HOOK
    const { 
        expenses, balance, loading, error, hasMore, loadingMore, loadMore, deleteExpense 
    } = useDashboardData();


    // OBSERVER LOGIC
    const observerTarget = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Congelamos la referencia del observer en una constante local
        const currentTarget = observerTarget.current;

        const observer = new IntersectionObserver( entries => {
                // Si el espia entra en la pantalla y hay mas paginas por cargar..
                if (entries[0].isIntersecting && hasMore && !loadingMore){
                    loadMore(); // Llamamos a la API
                }
            },
            { threshold: 0.8 } // Se dispara cuando el div es visible 
        );

        // Le decimos al espia que empiece a vigilar el div
        if (currentTarget){
            observer.observe(currentTarget);
        }

        // Ahora podemos limpiar el observer cuando el componente se destruye
        return () => {
            if (currentTarget) {
                observer.unobserve(currentTarget);
            }
        };
    }, [hasMore, loadingMore, loadMore]);

    // RENDERIZADO CONDICIONAL
    // Estado de carga inicial (pantalla completa vacia)
    if (loading && expenses.length === 0){
        return <div style={{ padding: '2rem', textAlign: 'center' }}>Cargando tu informacion...</div>;
    }

    if (error) {
        return <div style={{ color: 'red', padding: '20px' }}>ERROR: {error}</div>
    }

    return (
        <div style={{ padding: '20px', maxWidth: '480px', margin: '0 auto' }}>
            <header style={{ marginBottom: '20px' }}>
                <h1 style={{ fontSize: '1.2rem', color: 'var(--text-secondary)'}}>Hola, Ivan!
                </h1>
            </header>   

            { balance && < HeroBalance balance={balance} /> }
        

            <div className="list-container">
                {expenses.map(expense => (
                    <ExpenseItem
                    key={expense.id}
                    {...expense}
                    onDelete={deleteExpense}
                    />
                ))}
                {!loading && expenses.length === 0 && (
                    <p style={{ textAlign: 'center', color: '#6b7280' }}>
                    Aun no tienes gastos registrados. Anota el primero!
                    </p>
                )}

                <div
                ref={observerTarget}
                style={{ height: '40px', display: 'flex', justifyContent: 'center', alignItems: 'center', marginTop: '1rem' }}
                >
                    {loadingMore && <span style={{color: '#6b7280'}}>Cargando mas gastos...</span> }

                    {!hasMore && expenses.length > 0 && (
                        <span style={{ color: '#9ca3af', fontSize: '14px' }}>
                            Has llegado al final de tu historial
                        </span>
                    )}

                </div>
            </div>
            <FloatingActionButton />
        </div>
    );
}