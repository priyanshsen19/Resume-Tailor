import styles from '../styles/Home.module.css';

export default function QuotaCard({ quota }) {
  if (!quota) return null;
  const total = quota.keys.reduce((n, k) => n + k.daily_limit, 0);
  const used = Math.max(0, total - quota.requests_remaining_today);
  const pct = total ? Math.min(100, Math.round((used / total) * 100)) : 0;
  const fill = pct >= 90 ? styles.meterFillDanger : pct >= 70 ? styles.meterFillWarn : '';
  return (
    <section className={`${styles.card} ${styles.cardPad}`}>
      <div className={styles.cardTitle}>
        <span>Daily AI quota</span>
        <span>resets midnight PT</span>
      </div>
      <div className={styles.quotaBig}>
        <span className={styles.quotaNum}>{quota.requests_remaining_today}</span>
        <span className={styles.hint}>of {total} requests left today</span>
      </div>
      <div className={styles.meter}><div className={`${styles.meterFill} ${fill}`} style={{ width: `${pct}%` }} /></div>
    </section>
  );
}
