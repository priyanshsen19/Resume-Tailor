import { useEffect, useState } from 'react';
import styles from '../styles/Home.module.css';
import { Check } from './Icons';

export default function Progress({ steps, hint }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // Step 1 is client-side validation/upload and is done almost instantly;
  // everything after is one server round-trip we can't observe, so it stays active.
  const activeIdx = elapsed < 2 ? 0 : 1;

  return (
    <div className={`${styles.progress} ${styles.fadeIn}`} role="status" aria-live="polite">
      <div className={styles.progressBar} />
      <div className={styles.steps}>
        {steps.map((label, i) => {
          const done = i < activeIdx;
          const active = i === activeIdx;
          return (
            <div key={label} className={`${styles.step} ${done ? styles.stepDone : ''} ${active ? styles.stepActive : ''}`}>
              <span className={styles.stepIcon}>{done ? <Check width={11} height={11} /> : i + 1}</span>
              {label}
            </div>
          );
        })}
      </div>
      <div className={styles.elapsed}>
        <span>{hint}</span>
        <span>{elapsed}s</span>
      </div>
    </div>
  );
}
