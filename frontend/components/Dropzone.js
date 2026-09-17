import { useRef, useState } from 'react';
import styles from '../styles/Home.module.css';
import { Upload, Image as ImageIcon, FileText } from './Icons';

/**
 * Drag-and-drop file picker.
 *  - kind="image": shows thumbnails, enforces `max`
 *  - kind="tex":   single file chip
 */
export default function Dropzone({ kind = 'image', files, onChange, max = 3, accept, id }) {
  const [active, setActive] = useState(false);
  const [warning, setWarning] = useState(null);
  const inputRef = useRef(null);
  const multiple = kind === 'image';

  const addFiles = (incoming) => {
    setWarning(null);
    let list = Array.from(incoming || []);
    if (accept) {
      const exts = accept.split(',').map((a) => a.trim().toLowerCase());
      list = list.filter((f) =>
        exts.some((e) => (e.endsWith('/*') ? f.type.startsWith(e.slice(0, -1)) : f.name.toLowerCase().endsWith(e)))
      );
    }
    if (!multiple) {
      onChange(list.slice(0, 1));
      return;
    }
    const merged = [...files, ...list];
    if (merged.length > max) setWarning(`Only the first ${max} images are kept.`);
    onChange(merged.slice(0, max));
  };

  const onDrop = (e) => {
    e.preventDefault();
    setActive(false);
    addFiles(e.dataTransfer.files);
  };

  const remove = (idx) => onChange(files.filter((_, i) => i !== idx));

  return (
    <div>
      <div
        className={`${styles.dropzone} ${active ? styles.dropzoneActive : ''}`}
        onDragOver={(e) => { e.preventDefault(); setActive(true); }}
        onDragLeave={() => setActive(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          id={id}
          type="file"
          accept={accept}
          multiple={multiple}
          className={styles.hiddenInput}
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
          tabIndex={-1}
        />
        <div className={styles.dropzoneIcon}>{kind === 'image' ? <ImageIcon /> : <FileText />}</div>
        <div className={styles.dropzoneTitle}>
          <b>Click to upload</b> or drag &amp; drop
        </div>
        <div className={styles.dropzoneHint}>
          {kind === 'image' ? `PNG, JPG or WEBP · up to ${max} screenshots` : 'A single .tex file'}
        </div>
      </div>

      {warning && <p className={styles.hint} style={{ marginTop: 8 }}>{warning}</p>}

      {files.length > 0 && kind === 'image' && (
        <div className={styles.thumbs}>
          {files.map((f, i) => (
            <div className={styles.thumb} key={`${f.name}-${i}`}>
              <img src={URL.createObjectURL(f)} alt={f.name} onLoad={(e) => URL.revokeObjectURL(e.target.src)} />
              <button type="button" className={styles.removeBtn} onClick={() => remove(i)} aria-label={`Remove ${f.name}`}>×</button>
            </div>
          ))}
        </div>
      )}

      {files.length > 0 && kind === 'tex' && (
        <div className={styles.thumbs}>
          <div className={styles.fileChip}>
            <FileText width={16} height={16} />
            <span>{files[0].name}</span>
            <button type="button" className={styles.removeBtn} onClick={() => remove(0)} aria-label="Remove file">×</button>
          </div>
        </div>
      )}
    </div>
  );
}
