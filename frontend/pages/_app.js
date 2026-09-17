import { Inter } from 'next/font/google';
import '../styles/globals.css';

const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-sans' });

export default function App({ Component, pageProps }) {
  return (
    <div className={inter.variable} style={{ fontFamily: 'var(--font-sans)' }}>
      <Component {...pageProps} />
    </div>
  );
}
