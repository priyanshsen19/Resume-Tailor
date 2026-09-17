import styles from '../styles/Home.module.css';
import { absUrl } from '../lib/api';
import { Download, Refresh, Trash } from './Icons';

const initials = (name) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('');

const timeAgo = (iso) => {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return `${Math.floor(diff / 86400)} d ago`;
};

const expiresIn = (iso) => {
  if (!iso) return null;
  const mins = Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 60000));
  return mins < 60 ? `${mins} min left` : `${Math.round(mins / 60)} h left`;
};

export default function RecentResumes({ resumes, loading, onRecompile, onDelete, onRefresh }) {
  return (
    <section className={`${styles.card} ${styles.cardPad}`}>
      <div className={styles.cardTitle}>
        <span>Recent resumes</span>
        <button type="button" className={styles.iconBtn} onClick={onRefresh} aria-label="Refresh list" title="Refresh">
          <Refresh width={14} height={14} />
        </button>
      </div>

      {resumes.length === 0 ? (
        <div className={styles.empty}>{loading ? 'Loading…' : 'Nothing yet. Resumes you tailor show up here for 24 hours.'}</div>
      ) : (
        <div className={styles.list}>
          {resumes.map((r) => {
            const title = `${r.company} · ${r.role}`;
            const ttl = expiresIn(r.expires_at);
            return (
              <div className={styles.item} key={r.id}>
                <div className={styles.itemIcon}>{initials(r.company)}</div>
                <div className={styles.itemBody}>
                  <div className={styles.itemTitle} title={title}>{r.company}</div>
                  <div className={styles.itemSub} title={r.role}>{r.role}</div>
                  <div className={styles.itemSub}>{timeAgo(r.updated_at)}{ttl ? ` · ${ttl}` : ''}</div>
                </div>
                <div className={styles.itemActions}>
                  {r.pdf_download_url && (
                    <a className={styles.iconBtn} href={absUrl(r.pdf_download_url)} title="Download PDF" aria-label="Download PDF">
                      <Download width={14} height={14} />
                    </a>
                  )}
                  <button type="button" className={styles.iconBtn} onClick={() => onRecompile(r)} title="Recompile" aria-label="Recompile">
                    <Refresh width={14} height={14} />
                  </button>
                  <button type="button" className={`${styles.iconBtn} ${styles.iconBtnDanger}`} onClick={() => onDelete(r)} title="Delete" aria-label="Delete">
                    <Trash width={14} height={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
