import { useEffect, useState } from 'react';
import styles from '../styles/Home.module.css';
import { api, errorMessage } from '../lib/api';
import Dropzone from './Dropzone';
import { FileText, Refresh, Download } from './Icons';

/**
 * Edit the LaTeX the tailor starts from. The backend refuses anything that
 * does not compile, so a bad paste can never break tailoring.
 */
export default function BaseResume({ unlocked, withAccess, onSaved }) {
  const [tex, setTex] = useState('');
  const [original, setOriginal] = useState('');
  const [isCustom, setIsCustom] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [file, setFile] = useState([]);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/template', { timeout: 20000 });
      setTex(data.tex);
      setOriginal(data.tex);
      setIsCustom(data.is_custom);
    } catch (err) {
      setError(errorMessage(err, 'Could not load the base resume.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (unlocked) load(); else setLoading(false); }, [unlocked]);

  // Picking a .tex file loads it into the editor rather than uploading blind.
  useEffect(() => {
    if (!file[0]) return;
    file[0].text().then((t) => { setTex(t); setNotice(`Loaded ${file[0].name}. Review it, then save.`); setFile([]); });
  }, [file]);

  const save = async () => {
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      const form = new FormData();
      form.append('tex', tex);
      const { data } = await api.put('/template', form, { timeout: 120000 });
      setOriginal(tex);
      setIsCustom(true);
      setNotice(data.message);
      onSaved?.();
    } catch (err) {
      setError(errorMessage(err, 'Could not save the base resume.'));
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm('Discard your custom base resume and go back to the default?')) return;
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      await api.delete('/template', { timeout: 30000 });
      await load();
      setNotice('Reverted to the default template.');
      onSaved?.();
    } catch (err) {
      setError(errorMessage(err, 'Could not reset the base resume.'));
    } finally {
      setSaving(false);
    }
  };

  const download = () => {
    const url = URL.createObjectURL(new Blob([tex], { type: 'text/x-tex' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'base_resume.tex';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!unlocked) {
    return (
      <div className={styles.empty}>
        Private beta — <button type="button" className={styles.linkBtn} onClick={() => withAccess(() => {})}>enter your access code</button> to edit your base resume.
      </div>
    );
  }

  const dirty = tex !== original;

  return (
    <div className={styles.form}>
      <p className={styles.hint}>
        This is the LaTeX every tailored resume is built from — your details, sections and styling.
        Paste your own template or upload a <code className={styles.code}>.tex</code>; it&apos;s only saved if it compiles.
        {isCustom ? ' You are using your own template.' : ' You are using the built-in default.'}
      </p>

      <Dropzone kind="tex" accept=".tex" files={file} onChange={setFile} id="baseTex" />

      <div className={styles.field}>
        <label className={styles.label} htmlFor="baseTexArea">
          LaTeX source <small>{loading ? 'loading…' : `${tex.split('\n').length} lines${dirty ? ' · unsaved changes' : ''}`}</small>
        </label>
        <textarea
          id="baseTexArea"
          className={`${styles.textarea} ${styles.mono}`}
          value={tex}
          onChange={(e) => setTex(e.target.value)}
          spellCheck={false}
          disabled={loading}
        />
      </div>

      <div className={styles.actions}>
        <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={save} disabled={saving || loading || !dirty}>
          {saving ? <><span className={styles.spinner} /> Checking &amp; saving…</> : <><FileText width={16} height={16} /> Save base resume</>}
        </button>
        <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={download} disabled={loading}>
          <Download width={16} height={16} /> Download .tex
        </button>
        {isCustom && (
          <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={reset} disabled={saving}>
            <Refresh width={16} height={16} /> Use default
          </button>
        )}
      </div>

      {saving && <p className={styles.hint}>Compiling your template to make sure it works…</p>}
      {error && <div className={`${styles.alert} ${styles.alertError} ${styles.fadeIn}`} role="alert"><pre>{error}</pre></div>}
      {notice && <div className={`${styles.alert} ${styles.alertOk} ${styles.fadeIn}`}>{notice}</div>}
    </div>
  );
}
