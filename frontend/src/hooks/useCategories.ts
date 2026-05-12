/**
 * Hook para obtener las categorías disponibles del usuario.
 *
 * TODO (Backend - Fase 1): Conectar al endpoint GET /api/categories/
 * cuando esté disponible. El endpoint debe devolver:
 * [{ id: number, name: string, color: string }]
 *
 * Cuando el endpoint exista, reemplazar la inicialización directa
 * por un useEffect con fetch async y manejar loading/error correctamente.
 */

import { useState } from 'react';
import type { Category } from '../types';

const PLACEHOLDER_CATEGORIES: Category[] = [
  { id: 1,  name: 'Comida',          color: '#FF5733' },
  { id: 2,  name: 'Supermercado',    color: '#33FF57' },
  { id: 3,  name: 'Transporte',      color: '#3366FF' },
  { id: 4,  name: 'Delivery',        color: '#FF33F5' },
  { id: 5,  name: 'Servicios',       color: '#FFC300' },
  { id: 6,  name: 'Salud',           color: '#F38181' },
  { id: 7,  name: 'Entretenimiento', color: '#C70039' },
  { id: 8,  name: 'Ropa',            color: '#900C3F' },
  { id: 9,  name: 'Hogar',           color: '#581845' },
  { id: 10, name: 'Educación',       color: '#1E8449' },
];

interface UseCategoriesResult {
  categories: Category[];
  loading: boolean;
  error: string | null;
}

export function useCategories(): UseCategoriesResult {
  // Inicialización directa — sin useEffect porque los datos son estáticos por ahora.
  // Cuando conectes la API real, convertir a:
  //   const [categories, setCategories] = useState<Category[]>([]);
  //   const [loading, setLoading] = useState(true);
  //   const [error, setError] = useState<string | null>(null);
  //   useEffect(() => { fetchCategories(); }, []);
  const [categories] = useState<Category[]>(PLACEHOLDER_CATEGORIES);

  return {
    categories,
    loading: false,
    error: null,
  };
}