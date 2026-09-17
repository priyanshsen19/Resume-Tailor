const base = { width: 18, height: 18, fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' };

export const Sparkles = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8z"/></svg>
);
export const Upload = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 16V4"/><path d="M6 10l6-6 6 6"/><path d="M4 20h16"/></svg>
);
export const FileText = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/></svg>
);
export const Download = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M12 4v12"/><path d="M6 10l6 6 6-6"/><path d="M4 20h16"/></svg>
);
export const External = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>
);
export const Refresh = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/></svg>
);
export const Image = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-9 9"/></svg>
);
export const Check = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M5 12l5 5L20 7"/></svg>
);
export const Logo = (p) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" {...p}><path d="M6 3h8l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 1.5V9h4.5L13 4.5zM8 12h8v1.6H8V12zm0 3.2h8v1.6H8v-1.6zm0 3.2h5v1.6H8v-1.6z"/></svg>
);
export const Trash = (p) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/></svg>
);
