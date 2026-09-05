import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/auth';
import { jobsApi, type Job } from '../../lib/api';
import Button from '../../components/ui/Button';
import ForgeButton from '../../components/ui/ForgeButton';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import { Upload, Link as LinkIcon, Scissors, ArrowRight, Play } from 'lucide-react';
import { motion } from 'framer-motion';

function formatTime(s: number | null | undefined): string {
  if (!Number.isFinite(s)) return '—';
  const v = Number(s);
  return `${Math.floor(v / 60)}:${(v % 60).toFixed(1).padStart(4, '0')}`;
}

function formatDate(ts?: number): string {
  return ts ? new Date(ts * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '';
}

function fileSize(b: number): string {
  return b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`;
}

const stagger = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.06 } } };
const fadeUp = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function Dashboard() {
  const { user, credits, fetchCredits } = useAuthStore();
  const navigate = useNavigate();
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState('');
  const [forging, setForging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    jobsApi.list().then(setJobs).catch(() => {});
    fetchCredits();
  }, []);

  const forgeUrl = async () => {
    if (!url.trim()) { setError('Paste a YouTube URL or choose a file.'); return; }
    setError(''); setForging(true);
    try {
      const r = await jobsApi.createYouTube(url.trim());
      navigate(`/processing/${r.job_id}`);
    } catch (e: any) {
      setError(e.message);
    } finally { setForging(false); }
  };

  const forgeFile = async () => {
    if (!file) return;
    setError(''); setForging(true);
    try {
      const r = await jobsApi.upload(file);
      navigate(`/processing/${r.job_id}`);
    } catch (e: any) {
      setError(e.message);
    } finally { setForging(false); }
  };

  const doneJobs = jobs.filter(j => j.stage === 'done');
  const clipCount = doneJobs.reduce((n, j) => n + j.clips.filter(c => c.status === 'done').length, 0);
  const recentClips = doneJobs.flatMap(j => j.clips.filter(c => c.status === 'done').map(c => ({ ...c, _job: j }))).slice(0, 4);

  return (
    <div className="max-w-5xl mx-auto px-5 md:px-14 py-10">
      <motion.div initial="hidden" animate="show" variants={stagger}>
        {/* Hero */}
        <motion.div variants={fadeUp} className="mb-8">
          <h1 className="text-[2rem] md:text-[2.5rem] font-bold tracking-[-0.04em] leading-tight text-clpz-text-primary">
            {user ? (
              <>Welcome back, <span className="text-clpz-accent">{user.display_name || user.email.split('@')[0]}</span>.</>
            ) : 'Dashboard'}
          </h1>
          <p className="mt-2 text-[15px] text-clpz-text-secondary max-w-md">
            Paste a YouTube URL or drop a video to forge clips.
          </p>
        </motion.div>

        {/* Stats */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {[
            { label: 'Credits', value: credits.toString(), accent: true },
            { label: 'Projects', value: doneJobs.length.toString() },
            { label: 'Clips made', value: clipCount.toString(), success: true },
            { label: 'Per forge', value: '1' },
          ].map((s) => (
            <div key={s.label} className="p-4 bg-clpz-surface-1 border border-clpz-border rounded-xl">
              <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-clpz-text-tertiary">{s.label}</span>
              <strong className={`block mt-2 text-xl font-bold tracking-tight ${s.accent ? 'text-clpz-accent' : s.success ? 'text-clpz-success' : 'text-clpz-text-primary'}`}>
                {s.value}
              </strong>
            </div>
          ))}
        </motion.div>

        {/* Quick Forge */}
        <motion.div variants={fadeUp} className="mb-10">
          <h2 className="text-lg font-bold tracking-tight mb-3">Forge</h2>
          <div className="p-5 bg-clpz-surface-1 border border-clpz-border rounded-xl">
            {/* URL input */}
            <div className="flex items-center gap-3 p-1.5 pl-4 border border-clpz-border rounded-full bg-clpz-surface-inset focus-within:border-clpz-accent/40 transition-colors">
              <LinkIcon size={18} className="text-clpz-text-tertiary flex-shrink-0" />
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && forgeUrl()}
                placeholder="Paste YouTube URL..."
                className="flex-1 min-w-0 bg-transparent border-none outline-none text-clpz-text-primary text-sm placeholder:text-clpz-text-tertiary"
              />
              <ForgeButton onClick={forgeUrl} disabled={forging} size="sm">
                {forging ? 'Forging…' : '✦ Forge'}
              </ForgeButton>
            </div>

            {/* Divider */}
            <div className="flex items-center gap-4 my-4 text-clpz-text-tertiary text-[10px] font-semibold uppercase tracking-[0.2em]">
              <div className="flex-1 h-px bg-clpz-border" />
              <span>or</span>
              <div className="flex-1 h-px bg-clpz-border" />
            </div>

            {/* Upload */}
            <input ref={fileRef} type="file" accept="video/*" className="hidden" onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} />
            {!file ? (
              <button
                onClick={() => fileRef.current?.click()}
                className="w-full min-h-[100px] border border-dashed border-clpz-border rounded-xl p-5 text-center cursor-pointer bg-clpz-surface-2 hover:border-clpz-accent/40 hover:bg-clpz-accent/[0.02] transition-all group"
              >
                <div className="grid place-items-center w-10 h-10 mx-auto border border-clpz-border rounded-xl bg-clpz-surface-1 text-clpz-text-secondary mb-3 group-hover:text-clpz-accent group-hover:border-clpz-accent/30 transition-colors">
                  <Upload size={18} />
                </div>
                <h3 className="text-sm font-semibold text-clpz-text-primary">Drop a video here</h3>
                <p className="text-xs text-clpz-text-tertiary mt-1">or click to browse</p>
              </button>
            ) : (
              <div className="flex items-center gap-3.5 p-3.5 border border-clpz-accent/30 rounded-xl bg-clpz-accent/[0.03]">
                <div className="grid place-items-center w-10 h-10 rounded-xl bg-clpz-accent/15 text-clpz-accent flex-shrink-0">
                  <Play size={18} fill="currentColor" />
                </div>
                <div className="flex-1 min-w-0">
                  <strong className="block text-sm truncate text-clpz-text-primary">{file.name}</strong>
                  <span className="block mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-clpz-accent/70">{fileSize(file.size)} · ready</span>
                </div>
                <Button variant="ghost" size="sm" onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ''; }}>Change</Button>
                <ForgeButton onClick={forgeFile} disabled={forging} size="sm">
                  {forging ? 'Uploading…' : '✦ Forge'}
                </ForgeButton>
              </div>
            )}
            <p className="mt-3 text-[10px] font-semibold uppercase tracking-wider text-clpz-text-tertiary text-center">MP4 · MOV · MKV · WebM · AVI</p>
            {error && <p className="mt-2.5 text-xs text-clpz-error">{error}</p>}
          </div>
        </motion.div>

        {/* Recent projects */}
        <motion.div variants={fadeUp}>
          <div className="flex items-end justify-between mb-3">
            <div>
              <h2 className="text-lg font-bold tracking-tight">Recent projects</h2>
              <p className="text-xs text-clpz-text-secondary mt-0.5">Your latest forged projects.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {jobs.slice(0, 3).map(j => {
              const count = j.clips.filter(c => c.status === 'done').length;
              const title = j.video?.title || (j.input_type === 'upload' ? 'Uploaded video' : 'YouTube video');
              return (
                <Card key={j.id} hover className="overflow-hidden cursor-pointer" onClick={() => navigate(`/clips/${j.id}`)}>
                  <div className="h-20 p-5 bg-clpz-surface-2 flex items-end relative">
                    <span className="grid place-items-center w-9 h-9 border border-clpz-border/50 rounded-xl bg-black/30 text-clpz-accent">
                      <Scissors size={14} />
                    </span>
                    <span className="absolute right-4 bottom-3 text-[10px] font-semibold uppercase tracking-wider text-white/50">{count} clip{count !== 1 ? 's' : ''}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2.5 p-3.5">
                    <div className="min-w-0 flex-1">
                      <strong className="block text-sm truncate">{title}</strong>
                      <small className="block mt-1 text-xs text-clpz-text-tertiary">{formatDate(j.created_at)}</small>
                    </div>
                    <ArrowRight size={14} className="text-clpz-text-tertiary flex-shrink-0" />
                  </div>
                </Card>
              );
            })}
          </div>
          {jobs.length === 0 && (
            <div className="flex flex-col items-center justify-center min-h-[180px] p-8 text-center border border-dashed border-clpz-border rounded-xl">
              <div className="grid place-items-center w-11 h-11 border border-clpz-border rounded-xl bg-clpz-surface-2 text-clpz-text-secondary mb-3">▣</div>
              <h3 className="text-base font-semibold">No projects yet</h3>
              <p className="text-sm text-clpz-text-secondary mt-1.5 max-w-xs">Paste a YouTube URL or upload a video above to get started.</p>
            </div>
          )}
        </motion.div>

        {/* Recent clips */}
        {recentClips.length > 0 && (
          <motion.div variants={fadeUp} className="mt-10">
            <h2 className="text-lg font-bold tracking-tight mb-3">Recent clips</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {recentClips.map((clip) => {
                const dur = clip.duration ?? clip.validation?.duration;
                return (
                  <div key={`${clip._job.id}-${clip.index}`} className="overflow-hidden border border-clpz-border rounded-xl bg-clpz-surface-1 transition-all hover:border-clpz-border-strong hover:-translate-y-0.5 group">
                    <button className="relative block w-full aspect-[9/16] bg-clpz-surface-2 text-left border-0 p-0 cursor-pointer" onClick={() => navigate(`/clips/${clip._job.id}`)}>
                      {clip.thumbnail_url && <img src={clip.thumbnail_url} alt="" className="w-full h-full object-cover opacity-88" loading="lazy" />}
                      <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/70" />
                      <span className="absolute top-2 left-2"><Badge variant="accent">9:16</Badge></span>
                      <span className="absolute bottom-2 left-2 right-2 flex justify-between text-[10px] font-mono text-white/80">
                        <span>9:16</span><span>{dur != null ? formatTime(dur) : '—'}</span>
                      </span>
                    </button>
                    <div className="p-3">
                      <div className="text-sm font-semibold truncate">{clip.title || `Clip ${clip.index + 1}`}</div>
                      <div className="text-xs text-clpz-text-tertiary mt-1 font-mono">{formatTime(clip.start)} — {formatTime(clip.end)}</div>
                      <div className="grid grid-cols-2 gap-1.5 mt-2.5">
                        <button className="rounded-lg py-1.5 px-2 text-xs font-semibold bg-clpz-accent/10 text-clpz-accent border-0 cursor-pointer hover:bg-clpz-accent/20 transition-colors" onClick={() => navigate(`/clips/${clip._job.id}`)}>Edit</button>
                        <a href={clip.download_url} className="rounded-lg py-1.5 px-2 text-xs font-semibold border border-clpz-border text-clpz-text-secondary bg-transparent text-center no-underline hover:bg-clpz-surface-2 transition-colors">↓ Download</a>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
