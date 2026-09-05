import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { jobsApi, type Job } from '../../lib/api';
import Badge from '../../components/ui/Badge';
import { Circle } from 'lucide-react';

const stages = [
  { key: 'downloading', label: 'Downloading', detail: 'Fetching source video' },
  { key: 'transcribing', label: 'Transcribing', detail: 'Creating word timestamps' },
  { key: 'analyzing', label: 'Finding moments', detail: 'Selecting clip candidates' },
  { key: 'tracking', label: 'Tracking speakers', detail: 'Planning face-aware crops' },
  { key: 'rendering', label: 'Rendering', detail: 'Burning captions into MP4s' },
  { key: 'finalizing', label: 'Finalizing', detail: 'Verifying files and media streams' },
  { key: 'done', label: 'Completed', detail: 'Playable clips are ready' },
];

const stageAliases: Record<string, string> = { queued: 'downloading', parsing: 'transcribing', error: 'error', cancelled: 'cancelled' };

function currentStage(j: Job) { return stageAliases[j?.stage] || j?.stage || 'downloading'; }
function stageIndex(k: string) { return stages.findIndex(s => s.key === k); }
function stageDetail(s: string) { return stages.find(i => i.key === s)?.detail || 'Processing video'; }

function formatElapsed(s: number) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
}

export default function Processing() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now() / 1000);
  const pollRef = useRef<ReturnType<typeof setInterval>>(null);

  useEffect(() => {
    if (!jobId) return;
    startRef.current = Date.now() / 1000;
    const timer = setInterval(() => setElapsed(Math.max(0, Date.now() / 1000 - startRef.current)), 1000);

    const poll = async () => {
      try {
        const j = await jobsApi.get(jobId);
        setJob(j);
        if (j.started_at) startRef.current = j.started_at;
        if (j.stage === 'done') { clearInterval(timer); if (pollRef.current) clearInterval(pollRef.current); navigate(`/clips/${jobId}`); }
        if (j.stage === 'error' || j.stage === 'cancelled') { clearInterval(timer); if (pollRef.current) clearInterval(pollRef.current); }
      } catch {}
    };
    poll();
    pollRef.current = setInterval(poll, 1000);

    return () => { clearInterval(timer); if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId]);

  const cs = job ? currentStage(job) : 'downloading';
  const ci = stageIndex(cs);
  const ex = typeof job?.progress === 'number' && job.progress > 0 && cs !== 'done';
  const pct = cs === 'done' ? 100 : ex ? Math.round(job!.progress! * 100) : 0;

  return (
    <div className="w-[min(580px,100%)] mx-auto pt-[clamp(60px,12vh,120px)] text-center">
      <Badge variant="accent"><Circle size={8} className="animate-pulse" /> In progress</Badge>
      <h1 className="mt-4 text-[clamp(30px,5vw,44px)] font-bold tracking-[-0.05em]">Forging your clips.</h1>
      <p className="mt-1.5 text-sm text-clpz-text-secondary">Every stage below comes directly from the media pipeline.</p>

      <div className="mt-8 p-6 border border-clpz-border rounded-2xl text-left bg-clpz-surface-1">
        <div className="flex items-center justify-between gap-4 pb-4 border-b border-clpz-border">
          <div>
            <strong className="text-sm">{stageDetail(cs)}</strong>
            <small className="block mt-1 text-[10px] font-semibold uppercase tracking-wider text-clpz-text-tertiary">Job {jobId?.slice(0, 8)}</small>
          </div>
          <span className="font-mono text-xs text-clpz-accent">
            {cs === 'done' ? 'Ready' : ex ? `${pct}%` : 'Working'}
          </span>
        </div>

        <div className="flex items-center justify-center gap-2.5 my-4">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-clpz-text-tertiary">Elapsed</span>
          <span className="font-mono text-[clamp(26px,5vw,38px)] font-bold text-clpz-accent tracking-wider">
            {cs === 'done' ? '✓ ' : ''}{formatElapsed(elapsed)}
          </span>
        </div>

        <ol className="space-y-0.5">
          {stages.map((s, i) => {
            const done = cs === 'done' || (ci >= 0 && i < ci);
            const active = s.key === cs;
            return (
              <li key={s.key} className={`flex items-center gap-3 px-2 py-2.5 rounded-[10px] text-sm ${active ? 'text-white bg-white/5' : done ? 'text-clpz-text-primary' : 'text-clpz-text-tertiary'}`}>
                <span className={`grid place-items-center w-[22px] h-[22px] rounded-full border text-[10px] flex-shrink-0 ${
                  done ? 'border-clpz-success/28 text-clpz-success bg-clpz-success/8'
                  : active ? 'border-clpz-accent/38 text-clpz-accent bg-clpz-accent/10 animate-pulse'
                  : 'border-white/10 text-clpz-text-tertiary'
                }`}>
                  {done ? '✓' : active ? '◌' : '·'}
                </span>
                <span>{s.label}</span>
                {active && (
                  <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-clpz-accent">
                    {ex ? `${pct}%` : 'Working'}
                  </span>
                )}
              </li>
            );
          })}
        </ol>

        <div className="h-[3px] mt-5 rounded-full bg-white/7 overflow-hidden">
          <div className="h-full rounded-full bg-clpz-accent transition-[width] duration-350" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <button
        className="mt-4 text-xs text-clpz-text-tertiary hover:text-white transition-colors cursor-pointer bg-transparent border-0"
        onClick={async () => { if (jobId) try { await jobsApi.cancel(jobId); } catch {} navigate('/'); }}
      >
        Cancel and return to Dashboard
      </button>
    </div>
  );
}
