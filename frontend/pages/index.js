import { useCallback, useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import styles from '../styles/Home.module.css';
import { api, errorMessage, getAccessCode, setAccessCode } from '../lib/api';
import { ensureSession } from '../lib/supabase';
import Dropzone from '../components/Dropzone';
import Progress from '../components/Progress';
import ResultPanel from '../components/ResultPanel';
import RecentResumes from '../components/RecentResumes';
import QuotaCard from '../components/QuotaCard';
import { Sparkles, Refresh, Logo } from '../components/Icons';

const REQUEST_TIMEOUT_MS = 600000; // backend may retry a slow Gemini call once (2 x 240s)
const NEW_UPLOAD = '__new__';

export default function Home() {
  const [tab, setTab] = useState('tailor');

  // Tailor form
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [jdText, setJdText] = useState('');
  const [jdImages, setJdImages] = useState([]);

  // Recompile form
  const [selectedId, setSelectedId] = useState('');
  const [rCompany, setRCompany] = useState('');
  const [rRole, setRRole] = useState('');
  const [rFile, setRFile] = useState([]);

  // Shared
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Backend + sidebar data
  const [backend, setBackend] = useState('checking'); // checking | online | waking | offline
  const [resumes, setResumes] = useState([]);
  const [loadingResumes, setLoadingResumes] = useState(false);
  const [quota, setQuota] = useState(null);
  const resultRef = useRef(null);
  // Shared access code: landing page is public, features need the code.
  const [codeRequired, setCodeRequired] = useState(false);
  const [needCode, setNeedCode] = useState(false);       // modal open?
  const [codeInput, setCodeInput] = useState('');
  const [codeError, setCodeError] = useState(null);
  const pendingRef = useRef(null);                       // action to run after unlocking
  const unlocked = () => !codeRequired || !!getAccessCode();

  const loadResumes = useCallback(async () => {
    setLoadingResumes(true);
    try {
      const { data } = await api.get('/resumes', { timeout: 20000 });
      setResumes(data.resumes || []);
    } catch {
      /* sidebar is best-effort */
    } finally {
      setLoadingResumes(false);
    }
  }, []);

  const loadQuota = useCallback(async () => {
    try {
      const { data } = await api.get('/keys', { timeout: 15000 });
      setQuota(data);
    } catch {
      setQuota(null);
    }
  }, []);

  // Anonymous Supabase session (no-op in local mode), then health check with
  // wake-up polling because free-tier hosts sleep when idle.
  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const ping = async () => {
      try {
        const { data } = await api.get('/health', { timeout: 8000 });
        if (cancelled) return;
        setBackend('online');
        setCodeRequired(!!data.access_code_required);
        if (data.access_code_required && !getAccessCode()) return;   // public landing; unlock on first action
        loadResumes();
        loadQuota();
      } catch {
        if (cancelled) return;
        attempts += 1;
        if (attempts >= 12) setBackend('offline');
        else {
          setBackend('waking');
          setTimeout(ping, 8000);
        }
      }
    };
    ensureSession()
      .catch((e) => {
        const msg = /anonymous sign-ins are disabled/i.test(e.message)
          ? 'Supabase is rejecting sign-ins: enable "Anonymous sign-ins" under Authentication → Sign In / Providers in the Supabase dashboard, then reload.'
          : `Could not start a session: ${e.message}`;
        setError(msg);
      })
      .finally(ping);
    return () => { cancelled = true; };
  }, [loadResumes, loadQuota]);

  useEffect(() => {
    if (result && resultRef.current) resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [result]);

  useEffect(() => {
    const id = api.interceptors.response.use(undefined, (err) => {
      if (err?.response?.status === 401 && /access code/i.test(err.response.data?.detail || '')) {
        setAccessCode('');
        setNeedCode(true);
      }
      return Promise.reject(err);
    });
    return () => api.interceptors.response.eject(id);
  }, []);

  /** Run `action` now if unlocked, otherwise ask for the code first and run it after. */
  const withAccess = (action) => {
    if (unlocked()) return action();
    pendingRef.current = action;
    setCodeError(null);
    setNeedCode(true);
    return undefined;
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setCodeError(null);
    setAccessCode(codeInput.trim());
    try {
      await api.get('/keys', { timeout: 15000 });
      setNeedCode(false);
      setCodeInput('');
      loadResumes();
      loadQuota();
      const run = pendingRef.current;
      pendingRef.current = null;
      if (run) run();
    } catch (err) {
      setAccessCode('');
      setCodeError(err?.response?.status === 401 ? 'Wrong code.' : errorMessage(err, 'Could not verify the code.'));
    }
  };

  const switchTab = (next) => {
    setTab(next);
    setError(null);
    setResult(null);
  };

  const submitTailor = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!company.trim() || !role.trim()) return setError('Company and role are required.');
    if (!jdText.trim() && jdImages.length === 0) return setError('Paste the job description or upload screenshots of it.');
    if (!unlocked()) return withAccess(() => submitTailor({ preventDefault() {} }));

    const form = new FormData();
    form.append('company', company.trim());
    form.append('role', role.trim());
    if (jdText.trim()) form.append('jd_text', jdText);
    jdImages.forEach((img) => form.append('jd_images', img));

    setLoading(true);
    try {
      const { data } = await api.post('/tailor', form, { timeout: REQUEST_TIMEOUT_MS });
      setResult(data);
      loadResumes();
      loadQuota();
    } catch (err) {
      setError(errorMessage(err, 'Failed to tailor the resume.'));
      loadQuota();
    } finally {
      setLoading(false);
    }
  };

  const submitRecompile = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    const isNew = selectedId === NEW_UPLOAD;
    if (!unlocked()) return withAccess(() => submitRecompile({ preventDefault() {} }));
    if (!selectedId) return setError('Pick a resume to recompile.');
    if (isNew && (!rFile[0] || !rCompany.trim() || !rRole.trim())) return setError('Upload a .tex file and enter company and role.');

    const form = new FormData();
    if (!isNew) form.append('resume_id', selectedId);
    if (rFile[0]) form.append('tex_file', rFile[0]);
    if (isNew) {
      form.append('company', rCompany.trim());
      form.append('role', rRole.trim());
    }

    setLoading(true);
    try {
      const { data } = await api.post('/recompile', form, { timeout: REQUEST_TIMEOUT_MS });
      setResult(data);
      loadResumes();
    } catch (err) {
      setError(errorMessage(err, 'Recompilation failed.'));
    } finally {
      setLoading(false);
    }
  };

  const deleteResume = async (r) => {
    if (!unlocked()) return withAccess(() => deleteResume(r));
    if (!window.confirm(`Delete "${r.company} · ${r.role}"? This can't be undone.`)) return;
    try {
      await api.delete(`/resumes/${encodeURIComponent(r.id)}`);
      setResumes((list) => list.filter((x) => x.id !== r.id));
      if (selectedId === r.id) setSelectedId('');
    } catch (err) {
      setError(errorMessage(err, 'Could not delete the resume.'));
    }
  };

  const clearTailor = () => { setCompany(''); setRole(''); setJdText(''); setJdImages([]); setResult(null); setError(null); };
  const clearRecompile = () => { setSelectedId(''); setRCompany(''); setRRole(''); setRFile([]); setResult(null); setError(null); };

  const useForRecompile = (r) => {
    switchTab('recompile');
    setSelectedId(r.id);
    setRFile([]);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const selectedResume = resumes.find((r) => r.id === selectedId);
  const showBackendPill = backend === 'waking' || backend === 'offline';

  return (
    <div className={styles.shell}>
      <Head>
        <title>Resume Tailor — AI-tailored LaTeX resumes</title>
        <meta name="description" content="Paste a job description, get a tailored, ATS-friendly PDF resume compiled from your LaTeX template." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='22' fill='%236366f1'/><text y='.9em' x='50' text-anchor='middle' font-size='62'>📄</text></svg>" />
      </Head>

      <header className={styles.topbar}>
        <div className={`${styles.container} ${styles.topbarInner}`}>
          <a className={styles.brand} href="/">
            <span className={styles.logo}><Logo /></span>
            Resume Tailor
          </a>
          <div className={styles.topbarRight}>
            {quota && (
              <span className={styles.pill} title="AI requests remaining today">
                <Sparkles width={14} height={14} /> {quota.requests_remaining_today} left today
              </span>
            )}
            {showBackendPill && (
              <span className={styles.pill}>
                <span className={`${styles.dot} ${backend === 'waking' ? styles.dotWaking : styles.dotOffline}`} />
                {backend === 'waking' ? 'Waking up the server…' : 'Server unreachable'}
              </span>
            )}
          </div>
        </div>
      </header>

      <main className={styles.container}>
        <section className={styles.hero}>
          <h1 className={styles.h1}>
            Tailor your resume to <span className={styles.gradientText}>any job</span> in one click.
          </h1>
          <p className={styles.lede}>
            Paste a job description — or drop in screenshots — and get an ATS-friendly PDF built from your own
            LaTeX template. Facts stay true; wording gets sharper.
          </p>
        </section>

        {needCode && (
          <div className={styles.backdrop} onClick={() => { setNeedCode(false); pendingRef.current = null; }}>
            <form className={`${styles.card} ${styles.cardPad} ${styles.gate} ${styles.fadeIn}`} onSubmit={submitCode} onClick={(e) => e.stopPropagation()}>
              <div className={styles.cardTitle}><span>Access code required</span></div>
              <p className={styles.hint}>This app is private. Enter the access code you were given to continue.</p>
              <input className={styles.input} type="password" placeholder="Access code" value={codeInput} onChange={(e) => setCodeInput(e.target.value)} autoFocus />
              {codeError && <div className={`${styles.alert} ${styles.alertError}`}>{codeError}</div>}
              <div className={styles.actions}>
                <button type="submit" className={`${styles.btn} ${styles.btnPrimary}`} disabled={!codeInput.trim()}>Unlock</button>
                <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={() => { setNeedCode(false); pendingRef.current = null; }}>Cancel</button>
              </div>
            </form>
          </div>
        )}

        <div className={styles.grid}>
          <section className={`${styles.card} ${styles.cardPad}`}>
            <div className={styles.tabs} role="tablist">
              <button role="tab" aria-selected={tab === 'tailor'} className={`${styles.tab} ${tab === 'tailor' ? styles.tabActive : ''}`} onClick={() => switchTab('tailor')}>
                Tailor new resume
              </button>
              <button role="tab" aria-selected={tab === 'recompile'} className={`${styles.tab} ${tab === 'recompile' ? styles.tabActive : ''}`} onClick={() => switchTab('recompile')}>
                Recompile
              </button>
            </div>

            {backend === 'offline' && (
              <div className={`${styles.alert} ${styles.alertWarn}`} style={{ marginBottom: 18 }}>
                <span>The server isn&apos;t responding right now. Please try again in a minute.</span>
              </div>
            )}

            {tab === 'tailor' && (
              <form className={styles.form} onSubmit={submitTailor}>
                <div className={styles.row}>
                  <div className={styles.field}>
                    <label className={styles.label} htmlFor="company">Company</label>
                    <input id="company" className={styles.input} placeholder="e.g. Stripe" value={company} onChange={(e) => setCompany(e.target.value)} autoComplete="organization" required />
                  </div>
                  <div className={styles.field}>
                    <label className={styles.label} htmlFor="role">Role</label>
                    <input id="role" className={styles.input} placeholder="e.g. Senior Backend Engineer" value={role} onChange={(e) => setRole(e.target.value)} required />
                  </div>
                </div>

                <div className={styles.field}>
                  <label className={styles.label} htmlFor="jd">
                    Job description <small>{jdText.trim() ? `${jdText.trim().split(/\s+/).length} words` : 'paste the full posting for best results'}</small>
                  </label>
                  <textarea id="jd" className={styles.textarea} placeholder="Paste the full job description here…" value={jdText} onChange={(e) => setJdText(e.target.value)} />
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>Screenshots <small>optional · used when the JD can&apos;t be copied</small></label>
                  <Dropzone kind="image" accept="image/*" max={3} files={jdImages} onChange={setJdImages} id="jdImages" />
                </div>

                <div className={styles.actions}>
                  <button type="submit" className={`${styles.btn} ${styles.btnPrimary}`} disabled={loading || backend === 'offline'}>
                    {loading ? <><span className={styles.spinner} /> Tailoring…</> : <><Sparkles width={16} height={16} /> Tailor resume</>}
                  </button>
                  <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={clearTailor} disabled={loading}>Clear</button>
                </div>

                {loading && (
                  <Progress
                    steps={['Uploading job description', 'Tailoring & compiling PDF']}
                    hint="Usually 30–90 seconds. Longer if the server was asleep."
                  />
                )}
                {error && <div className={`${styles.alert} ${styles.alertError} ${styles.fadeIn}`} role="alert"><pre>{error}</pre></div>}
                <div ref={resultRef}>{result && <ResultPanel result={result} />}</div>
              </form>
            )}

            {tab === 'recompile' && (
              <form className={styles.form} onSubmit={submitRecompile}>
                <p className={styles.hint}>
                  Pick one of your recent resumes to rebuild its PDF. Optionally upload a hand-edited{' '}
                  <code className={styles.code}>.tex</code> to replace it — it goes through the same sanitiser and auto-repair.
                </p>

                <div className={styles.field}>
                  <label className={styles.label} htmlFor="resumeSelect">Resume</label>
                  <select id="resumeSelect" className={styles.select} value={selectedId} onChange={(e) => { setSelectedId(e.target.value); setError(null); }}>
                    <option value="">{loadingResumes ? 'Loading…' : resumes.length ? 'Choose a resume…' : 'No recent resumes'}</option>
                    {resumes.map((r) => (
                      <option key={r.id} value={r.id}>{r.company} · {r.role}</option>
                    ))}
                    <option value={NEW_UPLOAD}>Upload a new .tex…</option>
                  </select>
                </div>

                {selectedId === NEW_UPLOAD && (
                  <div className={`${styles.row} ${styles.fadeIn}`}>
                    <div className={styles.field}>
                      <label className={styles.label} htmlFor="rCompany">Company</label>
                      <input id="rCompany" className={styles.input} placeholder="e.g. Stripe" value={rCompany} onChange={(e) => setRCompany(e.target.value)} />
                    </div>
                    <div className={styles.field}>
                      <label className={styles.label} htmlFor="rRole">Role</label>
                      <input id="rRole" className={styles.input} placeholder="e.g. Senior Backend Engineer" value={rRole} onChange={(e) => setRRole(e.target.value)} />
                    </div>
                  </div>
                )}

                {selectedId && (
                  <div className={`${styles.field} ${styles.fadeIn}`}>
                    <label className={styles.label}>
                      Edited .tex file{' '}
                      <small>{selectedId === NEW_UPLOAD ? 'required' : `optional · leave empty to rebuild ${selectedResume ? selectedResume.company : 'it'} as-is`}</small>
                    </label>
                    <Dropzone kind="tex" accept=".tex" files={rFile} onChange={setRFile} id="texFile" />
                  </div>
                )}

                <div className={styles.actions}>
                  <button type="submit" className={`${styles.btn} ${styles.btnPrimary}`} disabled={loading || backend === 'offline' || !selectedId}>
                    {loading ? <><span className={styles.spinner} /> Compiling…</> : <><Refresh width={16} height={16} /> Recompile PDF</>}
                  </button>
                  <button type="button" className={`${styles.btn} ${styles.btnGhost}`} onClick={clearRecompile} disabled={loading}>Clear</button>
                </div>

                {loading && <Progress steps={['Uploading', 'Compiling PDF']} hint="Usually a few seconds." />}
                {error && <div className={`${styles.alert} ${styles.alertError} ${styles.fadeIn}`} role="alert"><pre>{error}</pre></div>}
                <div ref={resultRef}>{result && <ResultPanel result={result} />}</div>
              </form>
            )}
          </section>

          <aside className={styles.aside}>
            {unlocked() ? (
              <RecentResumes resumes={resumes} loading={loadingResumes} onRecompile={useForRecompile} onDelete={deleteResume} onRefresh={loadResumes} />
            ) : (
              <section className={`${styles.card} ${styles.cardPad}`}>
                <div className={styles.cardTitle}><span>Recent resumes</span></div>
                <div className={styles.empty}>
                  Private beta — <button type="button" className={styles.linkBtn} onClick={() => withAccess(() => {})}>enter your access code</button> to use the app.
                </div>
              </section>
            )}
            <QuotaCard quota={quota} />
            <section className={`${styles.card} ${styles.cardPad}`}>
              <div className={styles.cardTitle}><span>How it works</span></div>
              <ol className={styles.how}>
                <li className={styles.howItem}>The JD is analysed and your template&apos;s bullets are rewritten to match — never inventing experience.</li>
                <li className={styles.howItem}>The LaTeX is sanitised and compiled to PDF; if compilation fails it&apos;s repaired and retried automatically.</li>
                <li className={styles.howItem}>Download the PDF, or grab the .tex to fine-tune by hand and recompile.</li>
                <li className={styles.howItem}>Resumes are kept for 24 hours, then deleted.</li>
              </ol>
            </section>
          </aside>
        </div>
      </main>

      <footer className={styles.footer}>
        <div className={`${styles.container} ${styles.footerInner}`}>
          <span>Resume Tailor</span>
          <span>Files are deleted automatically after 24 hours.</span>
        </div>
      </footer>
    </div>
  );
}
