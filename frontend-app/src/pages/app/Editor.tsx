import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { jobsApi, type Clip } from '../../lib/api';
import Button from '../../components/ui/Button';
import { ArrowLeft, Undo2, Redo2 } from 'lucide-react';

function formatTime(s: number | null | undefined): string {
  if (!Number.isFinite(s)) return '—';
  const v = Number(s);
  return `${Math.floor(v / 60)}:${(v % 60).toFixed(1).padStart(4, '0')}`;
}

interface EditState {
  trim_start: number;
  trim_end: number | null;
  text_overlays: Array<{ text: string; x: number; y: number; size: number; color: string }>;
  volume: number;
  muted: boolean;
  speed: number;
}

const defaultState: EditState = { trim_start: 0, trim_end: null, text_overlays: [], volume: 1, muted: false, speed: 1 };

export default function Editor() {
  const { jobId, clipIndex } = useParams<{ jobId: string; clipIndex: string }>();
  const navigate = useNavigate();
  const [clip, setClip] = useState<Clip | null>(null);
  const [editState, setEditState] = useState<EditState>(defaultState);
  const [history, setHistory] = useState<EditState[]>([]);
  const [future, setFuture] = useState<EditState[]>([]);
  const [activeTool, setActiveTool] = useState('trim');
  const [toast, setToast] = useState('');

  useEffect(() => {
    if (jobId) {
      jobsApi.get(jobId).then(j => {
        const c = j.clips.find(cl => cl.index === Number(clipIndex));
        if (c) {
          setClip(c);
          const dur = c.duration ?? (c.end - c.start);
          const end = Math.round(dur * 10) / 10;
          setEditState(s => ({ ...s, trim_end: end }));
        }
      }).catch(() => navigate('/'));
    }
  }, [jobId, clipIndex]);

  const pushHistory = () => setHistory(h => [...h.slice(-49), { ...editState }]);
  const undo = () => {
    if (!history.length) return;
    setFuture(f => [...f, { ...editState }]);
    setEditState(history[history.length - 1]);
    setHistory(h => h.slice(0, -1));
  };
  const redo = () => {
    if (!future.length) return;
    setHistory(h => [...h, { ...editState }]);
    setEditState(future[future.length - 1]);
    setFuture(f => f.slice(0, -1));
  };

  const update = (patch: Partial<EditState>) => {
    pushHistory();
    setEditState(s => ({ ...s, ...patch }));
  };

  const exportEdit = async () => {
    if (!clip || !jobId) return;
    try {
      const r = await jobsApi.edit(jobId, clip.index, editState);
      setToast(`Saved to ${r.folder}`);
      setTimeout(() => setToast(''), 3000);
    } catch (e: any) { setToast(e.message); setTimeout(() => setToast(''), 3000); }
  };

  if (!clip) return <div className="min-h-screen flex items-center justify-center text-clpz-text-secondary">Loading…</div>;

  const dur = clip.duration ?? (clip.end - clip.start);
  const tools = ['trim', 'text', 'audio', 'speed'];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between gap-3.5 px-5 md:px-14 py-3 border-b border-clpz-border bg-clpz-surface-1">
        <button onClick={() => navigate(-1)} className="text-clpz-text-secondary hover:text-clpz-text-primary bg-transparent border-0 cursor-pointer text-sm flex items-center gap-1.5">
          <ArrowLeft size={14} /> Back
        </button>
        <div className="text-sm font-semibold truncate text-clpz-text-primary">{clip.title || `Clip ${clip.index + 1}`}</div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={undo} disabled={!history.length}><Undo2 size={14} /></Button>
          <Button size="sm" variant="secondary" onClick={redo} disabled={!future.length}><Redo2 size={14} /></Button>
          <Button size="sm" onClick={exportEdit}>Export</Button>
        </div>
      </header>

      {/* Main editor */}
      <div className="flex-1 grid grid-cols-[180px_1fr_270px] max-lg:grid-cols-1">
        {/* Tools sidebar */}
        <aside className="p-4 bg-clpz-surface-1 border-r border-clpz-border overflow-y-auto max-lg:hidden">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-clpz-text-tertiary">Tools</span>
          <div className="flex flex-col gap-0.5 mt-2">
            {tools.map(t => (
              <button
                key={t}
                onClick={() => setActiveTool(t)}
                className={`w-full text-left border-0 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors ${
                  activeTool === t ? 'text-clpz-accent bg-clpz-accent/10' : 'text-clpz-text-secondary bg-transparent hover:text-clpz-text-primary hover:bg-white/5'
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          <span className="text-[10px] font-semibold uppercase tracking-widest text-clpz-text-tertiary mt-4 block">Properties</span>
          <div className="mt-2">
            {activeTool === 'trim' && (
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs text-clpz-text-secondary mb-1">
                    <span>Start</span><span className="font-mono text-clpz-text-tertiary">{editState.trim_start.toFixed(1)}s</span>
                  </div>
                  <input type="range" min={0} max={Math.ceil(dur)} step={0.1} value={editState.trim_start}
                    onChange={e => setEditState(s => ({ ...s, trim_start: parseFloat(e.target.value) }))}
                    onMouseUp={() => pushHistory()}
                    className="w-full h-1 bg-white/10 rounded appearance-none cursor-pointer accent-clpz-accent"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-clpz-text-secondary mb-1">
                    <span>End</span><span className="font-mono text-clpz-text-tertiary">{(editState.trim_end ?? dur).toFixed(1)}s</span>
                  </div>
                  <input type="range" min={0} max={Math.ceil(dur)} step={0.1} value={editState.trim_end ?? dur}
                    onChange={e => setEditState(s => ({ ...s, trim_end: parseFloat(e.target.value) }))}
                    onMouseUp={() => pushHistory()}
                    className="w-full h-1 bg-white/10 rounded appearance-none cursor-pointer accent-clpz-accent"
                  />
                </div>
              </div>
            )}
            {activeTool === 'audio' && (
              <div>
                <div className="flex justify-between text-xs text-clpz-text-secondary mb-1">
                  <span>Volume</span><span className="font-mono text-clpz-text-tertiary">{editState.muted ? 'Muted' : `${Math.round(editState.volume * 100)}%`}</span>
                </div>
                <input type="range" min={0} max={200} value={editState.muted ? 0 : Math.round(editState.volume * 100)}
                  onChange={e => { const v = parseInt(e.target.value); setEditState(s => ({ ...s, volume: v / 100, muted: v === 0 })); }}
                  onMouseUp={() => pushHistory()}
                  className="w-full h-1 bg-white/10 rounded appearance-none cursor-pointer accent-clpz-accent"
                />
                <button onClick={() => update({ muted: !editState.muted, volume: editState.muted ? 1 : 0 })} className="mt-1.5 w-full text-xs text-clpz-text-secondary bg-transparent border-0 cursor-pointer hover:text-clpz-text-primary">
                  {editState.muted ? 'Unmute' : 'Mute'}
                </button>
              </div>
            )}
            {activeTool === 'speed' && (
              <div>
                <div className="flex justify-between text-xs text-clpz-text-secondary mb-1">
                  <span>Speed</span><span className="font-mono text-clpz-text-tertiary">{editState.speed}x</span>
                </div>
                <input type="range" min={25} max={400} value={Math.round(editState.speed * 100)}
                  onChange={e => setEditState(s => ({ ...s, speed: parseInt(e.target.value) / 100 }))}
                  onMouseUp={() => pushHistory()}
                  className="w-full h-1 bg-white/10 rounded appearance-none cursor-pointer accent-clpz-accent"
                />
                <div className="flex gap-1.5 mt-1.5">
                  {[50, 75, 100, 150, 200].map(s => (
                    <button key={s} onClick={() => update({ speed: s / 100 })} className={`flex-1 text-[11px] py-1 rounded bg-transparent border-0 cursor-pointer transition-colors ${editState.speed === s / 100 ? 'text-clpz-accent' : 'text-clpz-text-secondary hover:text-clpz-text-primary'}`}>
                      {s / 100}x
                    </button>
                  ))}
                </div>
              </div>
            )}
            {activeTool === 'text' && (
              <div className="space-y-2">
                <p className="text-xs text-clpz-text-tertiary">Text overlays will be applied on export.</p>
              </div>
            )}
          </div>
        </aside>

        {/* Preview */}
        <main className="flex items-center justify-center min-h-[500px] p-8 bg-clpz-canvas">
          <video
            src={clip.stream_url}
            controls
            preload="metadata"
            className="max-h-[65vh] max-w-full rounded-xl border border-clpz-border bg-clpz-surface-2"
          />
        </main>

        {/* Info panel */}
        <aside className="p-4 bg-clpz-surface-1 border-l border-clpz-border max-lg:border-t max-lg:border-l-0">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-clpz-text-tertiary">Caption data</span>
          <div className="mt-2 text-sm font-bold text-clpz-text-primary lowercase leading-snug">
            {(clip.caption_words || []).slice(0, 18).map(w => w.word).join(' ') || 'No caption words available.'}
          </div>
          <div className="mt-5 pt-4 border-t border-clpz-border space-y-2">
            {[
              ['Duration', formatTime(dur)],
              ['Source', `${formatTime(clip.start)} — ${formatTime(clip.end)}`],
              ['Crop', clip.layout || clip.render_plan?.mode || '—'],
            ].map(([label, val]) => (
              <div key={label} className="text-xs text-clpz-text-secondary">
                {label}<b className="block mt-0.5 text-clpz-text-primary">{val}</b>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed z-70 right-5 bottom-5 max-w-[360px] px-3.5 py-3 border border-clpz-border rounded-lg bg-clpz-surface-2 text-xs text-clpz-text-primary">
          {toast}
        </div>
      )}
    </div>
  );
}
