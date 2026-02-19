import { useState } from 'react';
import { Mail, ArrowRight } from 'lucide-react';
// import styles from './Login.module.css'; // (Crea este archivo CSS básico o usa estilos inline por ahora si prefieres rapidez)

export default function Login() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Enviando magic link a:", email);
    setSent(true);
    // Aquí luego llamaremos al backend real
  };

  if (sent) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', height: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ fontSize: '4rem', marginBottom: '20px' }}>📧</div>
        <h2>¡Revisa tu correo!</h2>
        <p style={{ color: '#64748b' }}>Te enviamos un enlace mágico a <strong>{email}</strong></p>
        <button onClick={() => setSent(false)} style={{ marginTop: '20px', background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer' }}>
          Intentar con otro correo
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px', height: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '10px' }}>Bienvenido 👋</h1>
      <p style={{ color: '#64748b', marginBottom: '40px' }}>Ingresa tu correo para entrar a SmartExpense.</p>

      <form onSubmit={handleSubmit}>
        <div style={{ position: 'relative', marginBottom: '20px' }}>
          <Mail size={20} style={{ position: 'absolute', left: '12px', top: '12px', color: '#94a3b8' }} />
          <input 
            type="email" 
            placeholder="tu@email.com" 
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ 
              width: '100%', padding: '12px 12px 12px 40px', fontSize: '1rem', 
              border: '1px solid #e2e8f0', borderRadius: '12px', outline: 'none' 
            }}
          />
        </div>

        <button 
          type="submit" 
          style={{ 
            width: '100%', padding: '14px', backgroundColor: 'var(--primary)', color: 'white', 
            border: 'none', borderRadius: '12px', fontSize: '1rem', fontWeight: 600,
            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px'
          }}
        >
          Enviar Enlace Mágico <ArrowRight size={20} />
        </button>
      </form>
    </div>
  );
}