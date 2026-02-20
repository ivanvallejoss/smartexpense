import { Outlet } from 'react-router-dom';
import BottomNav from './BottomNav';

export default function MainLayout(){
    return (
        <div style={{ paddingBottom: '80px' }}>
            {/* El paddingBottom evita que el contenido final quede tapado por la barra de navegacion fija. */}
            <Outlet/>
            <BottomNav/>
        </div>
    );
}