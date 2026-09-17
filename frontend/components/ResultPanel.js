import { useEffect, useState } from 'react';
import styles from '../styles/Home.module.css';
import { absUrl } from '../lib/api';
import { Download, External, FileText } from './Icons';

export default function ResultPanel({ result }) {
  const r = result.resume || {};
  const pdfInline = absUrl(r.pdf_url);
  const pdfDownload = absUrl(r.pdf_download_url);
  const tex = absUrl(r.tex_url);

  // Inline PDF viewers are unreliable on phones; start collapsed there.
  const [showPreview, setShowPreview] = useState(false);
  useEffect(() => { setShowPreview(window.innerWidth > 720); }, []);

  return (
    <div className={`${styles.result} ${styles.fadeIn}`}>
      <div className={styles.resultHead}>
        <div>
          <div className={styles.resultTitle}>
            <span className={styles.check}>✓</span>
            {result.message}
          </div>
          {r.expires_at && (
            <div className={styles.resultMeta}>Kept for 24 hours — download it now.</div>
          )}
        </div>
        <div className={styles.resultActions}>
          {pdfDownload && (
            <a className={`${styles.btn} ${styles.btnPrimary} ${styles.btnSm}`} href={pdfDownload}>
              <Download width={15} height={15} /> Download PDF
            </a>
          )}
          {tex && (
            <a className={`${styles.btn} ${styles.btnGhost} ${styles.btnSm}`} href={tex}>
              <FileText width={15} height={15} /> .tex
            </a>
          )}
          {pdfInline && (
            <a className={`${styles.btn} ${styles.btnGhost} ${styles.btnSm}`} href={pdfInline} target="_blank" rel="noreferrer">
              <External width={15} height={15} /> Open
            </a>
          )}
          {pdfInline && (
            <button type="button" className={`${styles.btn} ${styles.btnGhost} ${styles.btnSm}`} onClick={() => setShowPreview((v) => !v)}>
              {showPreview ? 'Hide preview' : 'Show preview'}
            </button>
          )}
        </div>
      </div>
      {showPreview && pdfInline && (
        <div className={styles.preview}>
          <object data={`${pdfInline}#toolbar=0&view=FitH`} type="application/pdf" aria-label="Resume preview">
            <div className={styles.previewFallback}>
              <p>This browser can&apos;t display PDFs inline.</p>
              <a className={`${styles.btn} ${styles.btnGhost} ${styles.btnSm}`} href={pdfInline} target="_blank" rel="noreferrer">
                <External width={15} height={15} /> Open the PDF
              </a>
            </div>
          </object>
        </div>
      )}
    </div>
  );
}
