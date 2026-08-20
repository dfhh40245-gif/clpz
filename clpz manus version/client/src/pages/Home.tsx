import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  Clock3,
  Crop,
  Download,
  FileVideo2,
  Image,
  Link2,
  LoaderCircle,
  Maximize2,
  MoreHorizontal,
  Music2,
  Play,
  Plus,
  Redo2,
  RotateCcw,
  Scissors,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Type,
  Undo2,
  Upload,
  Video,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { humanFileSize, isYouTubeUrl, processingStages } from "@/lib/clpz-state";

type Screen = "create" | "processing" | "clips" | "projects";
type Clip = { id: number; title: string; duration: string; score: number; start: string; end: string; theme: string };

const clips: Clip[] = [
  { id: 1, title: "The leverage moment", duration: "00:42", score: 94, start: "12:08", end: "12:50", theme: "from-[#28383b] via-[#182629] to-[#0e1213]" },
  { id: 2, title: "A better creative brief", duration: "00:31", score: 89, start: "18:22", end: "18:53", theme: "from-[#3a3129] via-[#24201d] to-[#111111]" },
  { id: 3, title: "When focus becomes output", duration: "00:57", score: 86, start: "23:14", end: "24:11", theme: "from-[#2c2939] via-[#1c1a26] to-[#101012]" },
  { id: 4, title: "The story people repeat", duration: "00:38", score: 82, start: "30:46", end: "31:24", theme: "from-[#343128] via-[#222018] to-[#11110e]" },
];

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5" aria-label="CLPZ">
      <span className="grid size-8 place-items-center rounded-[10px] border border-white/15 bg-white/[.055] text-[#f2c768] shadow-[inset_0_1px_0_rgba(255,255,255,.08)]"><Scissors size={15} strokeWidth={1.9} /></span>
      {!compact && <span className="text-[15px] font-semibold tracking-[-.04em] text-white">CLPZ</span>}
    </div>
  );
}

function Pill({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "gold" | "success" }) {
  const tones = {
    default: "border-white/10 bg-white/[.045] text-zinc-400",
    gold: "border-[#f2c768]/25 bg-[#f2c768]/10 text-[#f3cc77]",
    success: "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
  };
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[.12em] ${tones[tone]}`}>{children}</span>;
}

function ClipVisual({ clip, sourceUrl }: { clip: Clip; sourceUrl: string | null }) {
  return (
    <div className={`group relative aspect-[9/16] overflow-hidden rounded-[18px] bg-linear-to-b ${clip.theme}`}>
      {sourceUrl ? <video className="absolute inset-0 size-full object-cover opacity-70" src={sourceUrl} preload="none" muted playsInline /> : null}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_25%,rgba(255,255,255,.1),transparent_28%),linear-gradient(180deg,rgba(0,0,0,.03),rgba(0,0,0,.65))]" />
      <div className="absolute left-3 top-3"><Pill tone="gold">Score {clip.score}</Pill></div>
      <div className="absolute inset-x-3 bottom-3 flex items-end justify-between transition group-hover:opacity-0"><span className="font-mono text-[10px] tracking-[.12em] text-white/80">9:16</span><span className="font-mono text-[10px] text-white/80">{clip.duration}</span></div>
    </div>
  );
}

function ProcessingScreen({ stage, onCancel }: { stage: number; onCancel: () => void }) {
  return (
    <section className="motion-fade mx-auto flex min-h-[calc(100vh-82px)] max-w-xl flex-col justify-center px-5 pb-20">
      <div className="mb-10 text-center"><Pill tone="gold"><span className="size-1.5 rounded-full bg-[#f2c768]" /> In progress</Pill><h1 className="mt-5 text-3xl font-semibold tracking-[-.055em] text-white sm:text-4xl">Forging your clips.</h1><p className="mt-3 text-sm text-zinc-500">We’re shaping the best moments into vertical cuts.</p></div>
      <div className="glass-panel rounded-[24px] p-5 sm:p-7">
        <div className="mb-6 flex items-center justify-between border-b border-white/[.07] pb-5"><div><p className="text-sm font-medium text-zinc-200">Processing video</p><p className="mt-1 font-mono text-[10px] uppercase tracking-[.1em] text-zinc-600">Job CLPZ-042</p></div><span className="font-mono text-xs text-[#f2c768]">{Math.min(100, Math.round(((stage + 0.65) / processingStages.length) * 100))}%</span></div>
        <ol className="space-y-1" aria-label="Clip processing stages">
          {processingStages.map((name, index) => {
            const complete = index < stage;
            const active = index === stage;
            return <li key={name} className={`flex items-center gap-4 rounded-xl px-3 py-3.5 transition ${active ? "bg-white/[.055]" : ""}`}>
              <span className={`grid size-6 shrink-0 place-items-center rounded-full border ${complete ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : active ? "border-[#f2c768]/35 bg-[#f2c768]/10 text-[#f2c768]" : "border-white/10 text-zinc-600"}`}>{complete ? <Check size={13} /> : active ? <LoaderCircle size={13} className="animate-spin" /> : <span className="size-1.5 rounded-full bg-current" />}</span>
              <span className={`text-sm ${complete || active ? "text-zinc-100" : "text-zinc-600"}`}>{name}</span>
              {active && <span className="ml-auto font-mono text-[10px] uppercase tracking-[.14em] text-[#f2c768]">Working</span>}
            </li>;
          })}
        </ol>
        <div className="mt-6 h-1 overflow-hidden rounded-full bg-white/[.06]"><div className="h-full rounded-full bg-[#f2c768] transition-all duration-700" style={{ width: `${Math.min(100, ((stage + 0.5) / processingStages.length) * 100)}%` }} /></div>
      </div>
      <button onClick={onCancel} className="mx-auto mt-7 text-xs text-zinc-600 transition hover:text-zinc-200">Cancel and return to Create</button>
    </section>
  );
}

function EditorShell({ clip, sourceUrl, onBack }: { clip: Clip; sourceUrl: string | null; onBack: () => void }) {
  const [caption, setCaption] = useState("the moment that changes everything");
  const [size, setSize] = useState(42);
  const [position, setPosition] = useState(72);
  const tools = [{ name: "Text", icon: Type }, { name: "Image", icon: Image }, { name: "Music", icon: Music2 }, { name: "Crop", icon: Crop }];
  return <section className="motion-fade flex min-h-[calc(100vh-82px)] flex-col bg-[#0a0a0b]">
    <div className="border-b border-white/[.07] bg-[#0c0c0e] px-4 py-3 sm:px-6"><div className="mx-auto flex max-w-[1520px] items-center justify-between"><button onClick={onBack} className="inline-flex items-center gap-2 text-xs text-zinc-400 transition hover:text-white"><ArrowLeft size={14} /> Back to clips</button><div className="hidden items-center gap-2 sm:flex"><button onClick={() => toast("Nothing to undo yet.")} aria-label="Undo" className="grid size-8 place-items-center rounded-lg text-zinc-500 transition hover:bg-white/[.05] hover:text-white"><Undo2 size={14} /></button><button onClick={() => toast("Nothing to redo yet.")} aria-label="Redo" className="grid size-8 place-items-center rounded-lg text-zinc-500 transition hover:bg-white/[.05] hover:text-white"><Redo2 size={14} /></button><button onClick={() => toast.success("Export complete")} className="ml-2 inline-flex items-center gap-2 rounded-lg bg-[#f2c768] px-3.5 py-2 text-xs font-semibold text-[#201804] transition hover:bg-[#ffe198] active:scale-[.97]"><Download size={13} /> Export</button></div></div></div>
    <div className="mx-auto grid w-full max-w-[1520px] flex-1 grid-cols-1 lg:grid-cols-[188px_minmax(0,1fr)_278px]">
      <aside className="border-b border-white/[.07] bg-[#0d0d0f] p-4 lg:border-r lg:border-b-0"><p className="mb-3 px-2 font-mono text-[10px] uppercase tracking-[.14em] text-zinc-600">Tools</p><div className="grid grid-cols-4 gap-2 lg:grid-cols-1">{tools.map(({ name, icon: Icon }) => <button key={name} onClick={() => toast(`${name} editing will be available here.`)} className="flex flex-col items-center gap-2 rounded-xl border border-transparent p-2.5 text-xs text-zinc-400 transition hover:border-white/[.08] hover:bg-white/[.045] hover:text-white lg:flex-row"><Icon size={15} strokeWidth={1.7} /> <span>{name}</span></button>)}</div></aside>
      <main className="relative flex min-h-[470px] items-center justify-center overflow-hidden bg-[#09090a] p-8 sm:p-12"><div className="absolute inset-0 opacity-50 [background-image:radial-gradient(rgba(255,255,255,.08)_1px,transparent_1px)] [background-size:18px_18px]" /><div className="relative aspect-[9/16] h-[min(62vh,670px)] max-h-[670px] min-h-[330px] overflow-hidden rounded-[18px] border border-white/10 bg-[#18181b] shadow-[0_30px_70px_rgba(0,0,0,.5)]">{sourceUrl ? <video src={sourceUrl} className="size-full object-cover opacity-60" preload="metadata" controls /> : <div className={`size-full bg-linear-to-b ${clip.theme}`} />}<div className="absolute inset-x-[10%] pointer-events-none" style={{ top: `${position}%`, fontSize: `${Math.max(15, size * .38)}px` }}><p className="text-center font-bold leading-[.98] tracking-[-.055em] text-white drop-shadow-[0_2px_2px_rgba(0,0,0,.9)]">{caption}</p></div></div></main>
      <aside className="border-t border-white/[.07] bg-[#0d0d0f] p-5 lg:border-t-0 lg:border-l"><div className="flex items-center justify-between"><p className="font-mono text-[10px] uppercase tracking-[.14em] text-zinc-600">Properties</p><Settings2 size={14} className="text-zinc-600" /></div><div className="mt-5 border-b border-white/[.07] pb-4"><p className="text-xs font-medium text-zinc-200">Caption</p><textarea aria-label="Caption text" value={caption} onChange={(e) => setCaption(e.target.value)} className="mt-3 min-h-20 w-full resize-none rounded-xl border border-white/[.08] bg-white/[.035] p-3 text-xs leading-relaxed text-zinc-200 outline-none placeholder:text-zinc-600 focus:border-[#f2c768]/45" /></div><div className="space-y-5 pt-5"><label className="block"><span className="mb-2 flex justify-between text-xs text-zinc-400">Font <span className="text-zinc-600">Inter Bold</span></span><button className="flex w-full items-center justify-between rounded-lg border border-white/[.08] bg-white/[.035] px-3 py-2.5 text-left text-xs text-zinc-200">Inter Bold <ChevronRight size={13} className="text-zinc-600" /></button></label><label className="block"><span className="mb-2 flex justify-between text-xs text-zinc-400">Size <span className="font-mono text-zinc-600">{size}</span></span><input aria-label="Caption size" type="range" min="24" max="72" value={size} onChange={(e) => setSize(Number(e.target.value))} className="w-full accent-[#f2c768]" /></label><label className="block"><span className="mb-2 flex justify-between text-xs text-zinc-400">Position <span className="font-mono text-zinc-600">{position}%</span></span><input aria-label="Caption position" type="range" min="15" max="85" value={position} onChange={(e) => setPosition(Number(e.target.value))} className="w-full accent-[#f2c768]" /></label><div className="grid grid-cols-2 gap-2"><button onClick={() => toast("Caption color is set to white.")} className="rounded-lg border border-white/[.08] bg-white/[.035] p-2.5 text-xs text-zinc-400">Color <span className="ml-2 inline-block size-2.5 rounded-full border border-white/20 bg-white align-middle" /></button><button onClick={() => toast("Outline will be adjustable here.")} className="rounded-lg border border-white/[.08] bg-white/[.035] p-2.5 text-xs text-zinc-400">Outline</button></div></div></aside>
    </div>
    <div className="border-t border-white/[.07] bg-[#0d0d0f] px-4 py-4 sm:px-6"><div className="mx-auto max-w-[1520px]"><div className="mb-3 flex items-center justify-between"><p className="font-mono text-[10px] uppercase tracking-[.14em] text-zinc-600">Timeline</p><span className="font-mono text-[10px] text-zinc-500">{clip.duration}</span></div><div className="relative h-10 overflow-hidden rounded-lg border border-white/[.07] bg-white/[.025]"><div className="absolute inset-y-1 left-[4%] right-[18%] rounded-md border border-[#f2c768]/25 bg-[#f2c768]/10" /><div className="absolute inset-y-0 left-[39%] w-px bg-[#f2c768]" /><div className="absolute left-[39%] top-1 size-2 -translate-x-[3px] rounded-full bg-[#f2c768]" /></div></div></div>
  </section>;
}

export default function Home() {
  const [screen, setScreen] = useState<Screen>("create");
  const [url, setUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [stage, setStage] = useState(0);
  const [viewerClip, setViewerClip] = useState<Clip | null>(null);
  const [editorClip, setEditorClip] = useState<Clip | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);
  const [scrub, setScrub] = useState(27);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sourceUrlRef = useRef<string | null>(null);
  const viewerCloseRef = useRef<HTMLButtonElement>(null);

  useEffect(() => () => { if (sourceUrlRef.current) URL.revokeObjectURL(sourceUrlRef.current); }, []);
  useEffect(() => {
    if (screen !== "processing") return;
    if (stage >= processingStages.length) { const complete = window.setTimeout(() => setScreen("clips"), 620); return () => window.clearTimeout(complete); }
    const timer = window.setTimeout(() => setStage((current) => current + 1), 850);
    return () => window.clearTimeout(timer);
  }, [screen, stage]);
  useEffect(() => {
    if (!viewerClip) return;
    const focusTimer = window.setTimeout(() => viewerCloseRef.current?.focus(), 0);
    return () => window.clearTimeout(focusTimer);
  }, [viewerClip]);

  const selectFile = (file?: File) => {
    if (!file) return;
    if (!file.type.startsWith("video/")) { setError("Choose a video file to start forging."); return; }
    if (sourceUrlRef.current) URL.revokeObjectURL(sourceUrlRef.current);
    const nextUrl = URL.createObjectURL(file);
    sourceUrlRef.current = nextUrl;
    setSourceUrl(nextUrl); setSelectedFile(file); setError(null); setUrl("");
  };
  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => selectFile(event.target.files?.[0]);
  const onDrop = (event: DragEvent<HTMLButtonElement>) => { event.preventDefault(); setIsDragActive(false); selectFile(event.dataTransfer.files?.[0]); };
  const forge = () => {
    if (!selectedFile && !isYouTubeUrl(url)) { setError("Paste a valid YouTube URL or upload a video to continue."); return; }
    setError(null); setStage(0); setScreen("processing");
  };
  const resetCreate = () => { setScreen("create"); setError(null); };
  const clearFile = () => { if (sourceUrlRef.current) URL.revokeObjectURL(sourceUrlRef.current); sourceUrlRef.current = null; setSourceUrl(null); setSelectedFile(null); };
  const openEditor = (clip: Clip) => { setViewerClip(null); setEditorClip(clip); };
  const hasProject = screen === "clips" || stage > 0;

  if (editorClip) return <EditorShell clip={editorClip} sourceUrl={sourceUrl} onBack={() => setEditorClip(null)} />;

  return <div className="app-noise min-h-screen overflow-x-hidden bg-[#0a0a0b] text-zinc-100">
    <header className="sticky top-0 z-30 border-b border-white/[.06] bg-[#0a0a0b]/80 backdrop-blur-md"><div className="mx-auto flex h-[82px] max-w-[1440px] items-center justify-between px-5 sm:px-8"><button onClick={() => setScreen("create")} className="rounded-lg"><BrandMark /></button><nav aria-label="Primary navigation" className="flex items-center gap-1 rounded-xl border border-white/[.07] bg-white/[.025] p-1"><button onClick={() => setScreen("create")} className={`rounded-lg px-3 py-1.5 text-xs transition sm:px-4 ${screen === "create" || screen === "processing" ? "bg-white/[.08] text-white" : "text-zinc-500 hover:text-zinc-200"}`}>Create</button><button onClick={() => setScreen("projects")} className={`rounded-lg px-3 py-1.5 text-xs transition sm:px-4 ${screen === "projects" ? "bg-white/[.08] text-white" : "text-zinc-500 hover:text-zinc-200"}`}>Projects</button><button onClick={() => toast("Settings are coming soon.")} className="rounded-lg px-3 py-1.5 text-xs text-zinc-500 transition hover:text-zinc-200 sm:px-4">Settings</button></nav><button onClick={() => toast("A new project starts with a video.")} className="inline-flex items-center gap-2 rounded-lg border border-white/[.09] bg-white/[.045] px-3 py-2 text-xs text-zinc-300 transition hover:bg-white/[.08] active:scale-[.97]"><Plus size={13} /> <span className="hidden sm:inline">New project</span></button></div></header>

    {screen === "processing" ? <ProcessingScreen stage={stage} onCancel={resetCreate} /> : screen === "projects" ? <section className="motion-fade mx-auto max-w-[1180px] px-5 py-14 sm:px-8"><div className="flex items-end justify-between"><div><Pill>Workspace</Pill><h1 className="mt-4 text-3xl font-semibold tracking-[-.055em] text-white">Projects</h1><p className="mt-2 text-sm text-zinc-500">Your previous video-to-clip jobs, all in one place.</p></div><button onClick={() => setScreen("create")} className="hidden items-center gap-2 rounded-xl bg-[#f2c768] px-4 py-2.5 text-xs font-semibold text-[#201804] transition hover:bg-[#ffe198] active:scale-[.97] sm:inline-flex"><Plus size={14} /> Create project</button></div>{hasProject ? <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><button onClick={() => setScreen("clips")} className="group overflow-hidden rounded-[20px] border border-white/[.08] bg-white/[.03] text-left transition hover:-translate-y-1 hover:border-white/[.14] hover:bg-white/[.05]"><div className="relative h-36 overflow-hidden bg-linear-to-br from-[#2a3334] via-[#1a2021] to-[#101111]"><div className="absolute left-6 top-6 grid size-10 place-items-center rounded-xl border border-white/10 bg-black/25 text-[#f2c768]"><Clapperboard size={18} /></div><span className="absolute bottom-4 right-5 font-mono text-[10px] uppercase tracking-[.14em] text-white/55">4 clips</span></div><div className="flex items-center justify-between p-5"><div><p className="text-sm font-medium text-zinc-100">Untitled project</p><p className="mt-1 text-xs text-zinc-600">Created just now</p></div><ChevronRight size={16} className="text-zinc-600 transition group-hover:translate-x-0.5 group-hover:text-white" /></div></button></div> : <div className="mt-10 flex min-h-[320px] flex-col items-center justify-center rounded-[24px] border border-dashed border-white/[.11] bg-white/[.018] px-6 text-center"><span className="grid size-12 place-items-center rounded-2xl border border-white/[.09] bg-white/[.04] text-zinc-400"><FileVideo2 size={20} /></span><h2 className="mt-5 text-lg font-medium text-zinc-200">No projects yet.</h2><p className="mt-2 max-w-sm text-sm leading-relaxed text-zinc-500">Upload a video or paste a YouTube URL to start forging.</p><button onClick={() => setScreen("create")} className="mt-6 rounded-xl bg-[#f2c768] px-4 py-2.5 text-xs font-semibold text-[#201804] transition hover:bg-[#ffe198] active:scale-[.97]">Create your first project</button></div>}</section> : screen === "clips" ? <section className="motion-fade mx-auto max-w-[1240px] px-5 py-12 sm:px-8"><div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><div className="flex items-center gap-2"><Pill tone="success"><Check size={10} /> Complete</Pill><span className="font-mono text-[10px] uppercase tracking-[.12em] text-zinc-600">4 clips generated</span></div><h1 className="mt-4 text-3xl font-semibold tracking-[-.055em] text-white sm:text-4xl">Your clips</h1><p className="mt-2 text-sm text-zinc-500">The most compelling moments, ready to refine.</p></div><button onClick={() => { setStage(0); setScreen("create"); }} className="inline-flex w-fit items-center gap-2 rounded-xl border border-white/[.10] bg-white/[.035] px-4 py-2.5 text-xs text-zinc-300 transition hover:bg-white/[.07] active:scale-[.97]"><Plus size={14} /> Forge another</button></div><div className="mt-10 grid grid-cols-1 gap-5 min-[500px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{clips.map((clip, index) => <article key={clip.id} className="motion-rise group min-w-0" style={{ animationDelay: `${index * 55}ms` }}><div className="video-card-shadow overflow-hidden rounded-[21px] border border-white/[.08] bg-[#111113] transition duration-200 hover:-translate-y-1 hover:border-white/[.15] hover:shadow-[0_25px_45px_rgba(0,0,0,.38)]"><button onClick={() => setViewerClip(clip)} aria-label={`Open ${clip.title}`} className="block w-full text-left"><ClipVisual clip={clip} sourceUrl={sourceUrl} /></button><div className="p-4"><div className="flex justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-medium text-zinc-200">{clip.title}</p><p className="mt-1 font-mono text-[10px] tracking-[.08em] text-zinc-600">{clip.start} — {clip.end}</p></div><MoreHorizontal size={16} className="shrink-0 text-zinc-600" /></div><div className="mt-4 grid grid-cols-2 gap-2"><button onClick={() => openEditor(clip)} className="rounded-lg bg-white/[.09] px-3 py-2 text-xs font-medium text-zinc-100 transition hover:bg-white/[.15] active:scale-[.97]">Edit</button><button onClick={() => { toast("Downloading..."); window.setTimeout(() => toast.success("Downloaded successfully"), 650); }} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-white/[.1] px-3 py-2 text-xs text-zinc-400 transition hover:bg-white/[.06] hover:text-white active:scale-[.97]"><Download size={12} /> Download</button></div></div></div></article>)}</div></section> : <main className="motion-fade mx-auto flex min-h-[calc(100vh-82px)] max-w-[940px] flex-col items-center justify-center px-5 pb-20 pt-8 text-center"><div className="motion-rise"><Pill tone="gold"><Sparkles size={10} /> Video intelligence</Pill><h1 className="mt-6 text-[clamp(2.5rem,7vw,5rem)] font-semibold leading-[.92] tracking-[-.075em] text-white">Turn long videos<br />into clips.</h1><p className="mx-auto mt-5 max-w-md text-sm leading-relaxed text-zinc-500 sm:text-[15px]">Find the moments worth watching. Paste a video link or upload a file to begin.</p></div><div className="motion-rise mt-10 w-full max-w-[710px]" style={{ animationDelay: "80ms" }}><div className="glass-panel rounded-[22px] p-2"><div className="flex items-center gap-3 rounded-[15px] bg-black/20 px-3 py-2 sm:px-4"><Link2 size={17} className="shrink-0 text-zinc-500" /><input aria-label="YouTube URL" value={url} onChange={(event) => { setUrl(event.target.value); setError(null); if (event.target.value) clearFile(); }} onKeyDown={(event) => { if (event.key === "Enter") forge(); }} placeholder="Paste YouTube URL..." className="min-w-0 flex-1 bg-transparent py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-600" /><button onClick={forge} className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-[#f2c768] px-4 py-2.5 text-xs font-semibold text-[#201804] transition hover:bg-[#ffe198] active:scale-[.97] sm:px-5"><Sparkles size={13} /> Forge</button></div></div>{error && <div role="alert" className="mt-3 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-xs text-[#f1a5a1]"><AlertCircle size={13} /> {error}<button onClick={() => setError(null)} className="underline underline-offset-4 hover:text-white">Try again</button><button onClick={() => fileInputRef.current?.click()} className="underline underline-offset-4 hover:text-white">Upload video</button></div>}</div><div className="motion-rise my-7 flex w-full max-w-[710px] items-center gap-4" style={{ animationDelay: "120ms" }}><div className="h-px flex-1 bg-white/[.07]" /><span className="font-mono text-[10px] uppercase tracking-[.2em] text-zinc-600">or</span><div className="h-px flex-1 bg-white/[.07]" /></div><div className="motion-rise w-full max-w-[710px]" style={{ animationDelay: "160ms" }}><input ref={fileInputRef} onChange={onFileChange} type="file" accept="video/mp4,video/quicktime,video/x-matroska,video/webm,video/*" className="hidden" />{selectedFile ? <div className="glass-panel flex items-center gap-4 rounded-[20px] p-4 text-left sm:px-5"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-[#f2c768]/10 text-[#f2c768]"><Video size={19} /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-zinc-200">{selectedFile.name}</p><p className="mt-1 font-mono text-[10px] uppercase tracking-[.1em] text-zinc-600">{humanFileSize(selectedFile.size)} · video ready</p></div><button onClick={() => fileInputRef.current?.click()} className="hidden rounded-lg px-3 py-2 text-xs text-zinc-400 transition hover:bg-white/[.06] hover:text-white sm:block">Change</button><button onClick={clearFile} aria-label="Remove selected video" className="grid size-8 place-items-center rounded-lg text-zinc-600 transition hover:bg-white/[.06] hover:text-white"><X size={15} /></button><button onClick={forge} className="rounded-xl bg-[#f2c768] px-4 py-2.5 text-xs font-semibold text-[#201804] transition hover:bg-[#ffe198] active:scale-[.97]">Forge</button></div> : <button onClick={() => fileInputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setIsDragActive(true); }} onDragLeave={() => setIsDragActive(false)} onDrop={onDrop} className={`group w-full rounded-[21px] border border-dashed p-8 text-center transition sm:p-10 ${isDragActive ? "border-[#f2c768]/65 bg-[#f2c768]/[.06]" : "border-white/[.13] bg-white/[.018] hover:border-white/[.23] hover:bg-white/[.035]"}`}><span className="mx-auto grid size-11 place-items-center rounded-xl border border-white/[.1] bg-white/[.04] text-zinc-400 transition group-hover:text-[#f2c768]"><Upload size={18} /></span><p className="mt-4 text-sm font-medium text-zinc-300">Drop a video here</p><p className="mt-1 text-xs text-zinc-600">or click to browse</p></button>}<p className="mt-4 font-mono text-[10px] uppercase tracking-[.11em] text-zinc-600">MP4 · MOV · MKV · WebM</p></div><div className="mt-12 flex flex-wrap justify-center gap-x-7 gap-y-3 font-mono text-[10px] uppercase tracking-[.13em] text-zinc-600"><span className="inline-flex items-center gap-2"><Clapperboard size={12} /> Smart selection</span><span className="inline-flex items-center gap-2"><SlidersHorizontal size={12} /> Edit-ready</span><span className="inline-flex items-center gap-2"><Clock3 size={12} /> Vertical cuts</span></div></main>}

    {viewerClip && <div role="dialog" aria-modal="true" aria-label={`${viewerClip.title} preview`} onKeyDown={(event) => { if (event.key === "Escape") setViewerClip(null); }} className="motion-fade fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setViewerClip(null); }}><div className="glass-panel motion-rise relative grid max-h-[92vh] w-full max-w-[960px] overflow-auto rounded-[25px] md:grid-cols-[minmax(0,1fr)_280px]"><button ref={viewerCloseRef} onClick={() => setViewerClip(null)} aria-label="Close clip viewer" className="absolute right-4 top-4 z-10 grid size-8 place-items-center rounded-full border border-white/[.1] bg-black/30 text-zinc-400 backdrop-blur-sm transition hover:text-white"><X size={15} /></button><div className="flex min-h-[500px] items-center justify-center bg-[#09090a] p-8"><div className={`relative aspect-[9/16] h-[min(68vh,650px)] min-h-[360px] overflow-hidden rounded-[18px] bg-linear-to-b ${viewerClip.theme} shadow-[0_28px_58px_rgba(0,0,0,.52)]`}>{sourceUrl ? <video src={sourceUrl} preload="metadata" controls className="size-full object-cover" /> : <><div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(255,255,255,.12),transparent_30%)]" /><button onClick={() => setPlayingId(playingId === viewerClip.id ? null : viewerClip.id)} aria-label={`Play ${viewerClip.title}`} className="absolute left-1/2 top-1/2 grid size-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-white/20 bg-black/30 text-white backdrop-blur-sm transition hover:bg-white hover:text-black"><Play size={18} fill="currentColor" /></button></>}</div></div><aside className="border-t border-white/[.07] p-6 md:border-l md:border-t-0"><Pill tone="gold">Score {viewerClip.score}</Pill><h2 className="mt-4 text-xl font-semibold tracking-[-.04em] text-white">{viewerClip.title}</h2><p className="mt-2 text-sm leading-relaxed text-zinc-500">A high-retention segment selected for clarity, pace, and repeatable insight.</p><div className="mt-7 border-y border-white/[.07] py-5"><div className="mb-3 flex justify-between font-mono text-[10px] text-zinc-500"><span>00:00</span><span>{viewerClip.duration}</span></div><input aria-label="Clip timeline scrubber" type="range" min="0" max="100" value={scrub} onChange={(event) => setScrub(Number(event.target.value))} className="w-full accent-[#f2c768]" /><div className="mt-4 flex justify-between text-xs text-zinc-500"><span>{viewerClip.start}</span><span>{viewerClip.end}</span></div></div><div className="mt-5 grid grid-cols-2 gap-2"><button onClick={() => openEditor(viewerClip)} className="rounded-xl bg-white/[.1] px-3 py-2.5 text-xs font-medium text-white transition hover:bg-white/[.16]">Edit</button><button onClick={() => { toast("Downloading..."); window.setTimeout(() => toast.success("Downloaded successfully"), 650); }} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-white/[.1] px-3 py-2.5 text-xs text-zinc-400 transition hover:bg-white/[.05] hover:text-white"><Download size={13} /> Download</button></div></aside></div></div>}
  </div>;
}
