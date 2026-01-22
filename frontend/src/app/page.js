// 1. Importamos tu componente
import TransactionCard from '../components/ui/TransactionCard'; 
import HeroSectionCard from '../components/ui/HeroSectionCard';
// (Nota: verifica que la ruta sea correcta, a veces es '@/components/ui/TransactionCard')

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-100 p-8 flex flex-col items-center gap-4">
      
      <h1 className="text-3xl font-bold text-gray-800 mb-6">Mis Gastos</h1>

      <HeroSectionCard />
      {/* 2. Aquí usamos tu componente como si fuera una etiqueta HTML nueva */}
      <TransactionCard 
        merchant="Starbucks" 
        amount="4500" 
        category="Comida" 
        date="21 Ene" 
      />

      <TransactionCard 
        merchant="Uber" 
        amount="2300" 
        category="Transporte" 
        date="20 Ene" 
      />

      <TransactionCard 
        merchant="Carrefour" 
        amount="15400" 
        category="Supermercado" 
        date="19 Ene" 
      />

    </main>
  );
}