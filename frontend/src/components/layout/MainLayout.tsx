import { Outlet } from 'react-router-dom';
import BottomNav from './BottomNav';
import TopBar from './TopBar';

export default function MainLayout(){
    return (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
            <TopBar/>
            <main style={{ flex:1, padding: '0 1rem', paddingBottom: '6rem' }}>
                <Outlet/>
            </main>
            <BottomNav/>
        </div>
    );
}