import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { jobsApi, type Job, type Clip } from '../../lib/api';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import { ArrowLeft, Download, Edit } from 'lucide-react';

function formatTime(s: number | null | undefined): string {
  if (!Number.isFinite(s)) return '—';
  const v = Number(s);
  return `${Math.floor(v / 60)}:${(v % 60).toFixed(1).padStart(4, '0')}`;
}

export default function Clips() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [selectedClip, setSelectedClip] = useState<Clip | null>(null);

  useEffect(() => {
    if (jobId) jobsApi.get(jobId).then(setJob).catch(() => navigate('/'));
  }, [jobId]);

  const clips = job?.clips.filter(c => c.status === 'done') || [];

  return (
    <div className="max-w-5xl mx-auto px-5 md:px-14 py-12">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="text-clpz-text-secondary hover:text-clpz-text-primary transition-colors bg-transparent border-0 cursor-pointer">
            <ArrowLeft size={18} />
          </button>
          <div>
            <Badge variant="success">✓ Complete</Badge>
            <h1 className="text-2xl font-bold tracking-tight mt-2">Your clips</h1>
            <p className="text-xs text-clpz-text-secondary mt-0.5">
              {clips.length} real clip{clips.length !== 1 ? 's' : ''} from the verified render output.
            </p>
          </div>
        </div>
        <Button onClick={() => navigate('/')}>+ Forge another</Button>
      </div>

      {clips.length > 0 ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {clips.map((clip) => {
            const dur = clip.duration ?? clip.validation?.duration;
            return (
              <div key={clip.index} className="overflow-hidden border border-clpz-border rounded-xl bg-clpz-surface-1 transition-all hover:border-clpz-border-strong hover:-translate-y-0.5">
                <button className="relative block w-full aspect-[9/16] bg-clpz-surface-2 text-left border-0 p-0 cursor-pointer" onClick={() => setSelectedClip(clip)}>
                  {clip.thumbnail_url && <img src={clip.thumbnail_url} alt="" className="w-full h-full object-cover opacity-88" loading="lazy" />}
                  <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/70" />
                  <span className="absolute top-2.5 left-2.5"><Badge variant="accent">Verified</Badge></span>
                  <span className="absolute bottom-2.5 left-2.5 right-2.5 flex justify-between text-[10px] font-mono text-white/80">
                    <span>9:16</span><span>{dur != null ? formatTime(dur) : '—'}</span>
                  </span>
                </button>
                <div className="p-3.5">
                  <div className="text-sm font-semibold truncate">{clip.title || `Clip ${clip.index + 1}`}</div>
                  <div className="text-xs text-clpz-text-tertiary mt-1 font-mono">{formatTime(clip.start)} — {formatTime(clip.end)}</div>
                  <div className="grid grid-cols-2 gap-1.5 mt-3">
                    <button className="rounded-lg py-2 px-1.5 text-xs font-semibold bg-white/10 text-white border-0 cursor-pointer hover:bg-white/15 transition-colors flex items-center justify-center gap-1" onClick={() => navigate(`/editor/${jobId}/${clip.index}`)}>
                      <Edit size={12} /> Edit
                    </button>
                    <a href={clip.download_url} className="rounded-lg py-2 px-1.5 text-xs font-semibold border border-clpz-border text-clpz-text-secondary bg-transparent text-center no-underline hover:bg-white/5 transition-colors flex items-center justify-center gap-1">
                      <Download size={12} /> Download
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <Card className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
          <div className="grid place-items-center w-11 h-11 border border-clpz-border rounded-[14px] bg-clpz-surface-2 text-clpz-text-secondary mb-3.5">✂</div>
          <h3 className="text-base font-semibold">No completed clips</h3>
          <p className="text-sm text-clpz-text-secondary mt-1.5 max-w-xs">This job did not produce a playable clip yet.</p>
        </Card>
      )}

      {/* Clip preview modal */}
      {selectedClip && (
        <div className="fixed inset-0 z-40 flex items-center justify-center p-4.5 bg-black/76 backdrop-blur-sm" onClick={() => setSelectedClip(null)}>
          <div className="relative grid grid-cols-1 md:grid-cols-[1fr_280px] w-[min(950px,100%)] max-h-[92vh] overflow-auto border border-clpz-border rounded-2xl bg-clpz-surface-1" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-center min-h-[500px] p-8 bg-clpz-canvas">
              <video
                src={selectedClip.stream_url}
                controls
                preload="metadata"
                className="max-w-full max-h-[68vh] rounded-xl bg-clpz-surface-2"
              />
            </div>
            <div className="p-6 border-l border-clpz-border">
              <Badge variant="accent">Rendered clip</Badge>
              <h2 className="mt-3.5 text-xl tracking-tight font-semibold">{selectedClip.title || `Clip ${selectedClip.index + 1}`}</h2>
              <p className="mt-1.5 text-sm text-clpz-text-secondary leading-relaxed">{selectedClip.hook || 'Rendered from the selected transcript range.'}</p>

              <div className="mt-5 py-5 border-y border-clpz-border space-y-2">
                {[
                  ['Duration', formatTime(selectedClip.duration ?? selectedClip.validation?.duration)],
                  ['Source', `${formatTime(selectedClip.start)} — ${formatTime(selectedClip.end)}`],
                  ['Video', `${selectedClip.validation?.width || '—'}×${selectedClip.validation?.height || '—'} · ${selectedClip.validation?.video_codec || '—'}`],
                  ['Audio', selectedClip.validation?.audio_codec || '—'],
                ].map(([label, val]) => (
                  <div key={label} className="flex justify-between gap-3 text-[11px] font-mono text-clpz-text-secondary">
                    <span>{label}</span><b className="text-clpz-text-primary font-medium text-right">{val}</b>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-2 mt-5">
                <a href={selectedClip.download_url} className="rounded-[10px] py-2.5 px-2 text-xs font-semibold bg-clpz-accent text-clpz-canvas text-center no-underline">↓ Download</a>
                <button className="rounded-[10px] py-2.5 px-2 text-xs font-semibold border border-clpz-border bg-transparent text-clpz-text-primary cursor-pointer hover:bg-white/5 transition-colors">Save to Videos</button>
              </div>
            </div>
            <button
              className="absolute z-2 top-3 right-3 grid place-items-center w-[30px] h-[30px] rounded-full border border-clpz-border bg-clpz-surface-2 text-clpz-text-secondary hover:text-clpz-text-primary cursor-pointer"
              onClick={() => setSelectedClip(null)}
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
