import { useNavigate } from 'react-router-dom';
import ThemeToggle from '../../components/ui/ThemeToggle';
import HeroSection from '../../components/ui/HeroSection';
import { ChevronDown } from 'lucide-react';
import logoUrl from '../../assets/logo.png';

const howItWorks = [
  { num: '01', title: 'Upload or paste a link', desc: 'Drop in a video file or paste a YouTube URL. CLPZ handles the rest.' },
  { num: '02', title: 'Find the moments', desc: 'CLPZ reads the whole video for parts that stand on their own.' },
  { num: '03', title: 'Edit', desc: 'Trim, caption, reframe, and adjust — all in one editor.' },
  { num: '04', title: 'Export', desc: 'Download a clip that\'s ready to post, sized right for the platform.' },
];

const faq = [
  { q: 'How does CLPZ work?', a: 'CLPZ watches your entire video using local AI, identifies the best standalone moments, then generates captioned 9:16 clips ready to post — all on your machine.' },
  { q: 'Is my video uploaded to the cloud?', a: 'No. All processing happens locally on your computer. Your videos never leave your machine.' },
  { q: 'What video formats are supported?', a: 'MP4, MOV, MKV, WebM, and AVI. You can also paste a YouTube URL.' },
  { q: 'How many free clips do I get?', a: 'Every new account starts with 10 free clips. No credit card required.' },
  { q: 'Does it work on Windows?', a: 'Yes. CLPZ runs on Windows. Mac and Linux are planned.' },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white dark:bg-black dark:text-gray-100">
      {/* Nav — exact Qelvra nav */}
      <nav className="sticky top-0 z-40 border-b border-white/10 dark:border-white/10 bg-white/70 dark:bg-black/50 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 lg:px-8">
          <a href="/" className="flex items-center no-underline">
            <img src={logoUrl} alt="CLPZ" className="h-6 w-auto" />
          </a>
          <div className="hidden md:flex items-center gap-8">
            <a href="#process" className="text-[13px] font-medium text-gray-500 dark:text-gray-400 transition hover:text-gray-900 dark:hover:text-white">How it Works</a>
            <a href="#faq" className="text-[13px] font-medium text-gray-500 dark:text-gray-400 transition hover:text-gray-900 dark:hover:text-white">FAQ</a>
            <ThemeToggle />
            <button onClick={() => navigate('/auth?mode=signup')} className="glow-heartbeat-btn text-[13px]">Get CLPZ</button>
          </div>
        </div>
      </nav>

      {/* Hero — exact Qelvra HeroSection */}
      <HeroSection
        title="Turn long videos into clips worth posting."
        subtitle="CLPZ watches the full video, finds the moments that hold up on their own, and turns them into captioned, reframed clips — ready to edit and post."
        primaryButtonText="Get CLPZ"
        onPrimaryClick={() => navigate('/auth?mode=signup')}
      />

      {/* Trust bar */}
      <section className="border-y border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950 py-10">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-10 text-center">
          {[
            { value: '100% Local', label: 'Processing' },
            { value: '9:16', label: 'Auto-reframed' },
            { value: 'On-device', label: 'Transcription' },
            { value: 'Word-level', label: 'Captions' },
          ].map((stat, i) => (
            <div key={stat.label} className="flex items-center gap-10">
              {i > 0 && <div className="h-8 w-px bg-gray-200 dark:bg-gray-700" />}
              <div>
                <p className="text-xl font-bold tracking-tight text-gray-900 dark:text-white">{stat.value}</p>
                <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* How it Works — exact Qelvra section style */}
      <section id="process" className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <p className="mb-3 text-center text-[11px] font-semibold uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500">
            How it Works
          </p>
          <h2 className="mb-3 text-center text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
            From long video to finished short.
          </h2>
          <p className="mb-14 text-center text-sm text-gray-400 dark:text-gray-500">
            Four steps. No technical skills needed. Your computer does the heavy lifting.
          </p>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {howItWorks.map((step) => (
              <div key={step.num} className="rounded-lg p-7 border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
                <span className="text-sm font-bold text-amber-500 font-mono">{step.num}</span>
                <h3 className="mt-3 text-[15px] font-bold text-gray-900 dark:text-white">{step.title}</h3>
                <p className="mt-2 text-sm font-medium leading-relaxed text-gray-500 dark:text-gray-400">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ — exact Qelvra FAQ style */}
      <section id="faq" className="px-6 py-20 lg:px-8">
        <div className="mx-auto max-w-3xl">
          <p className="mb-3 text-center text-[11px] font-semibold uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500">
            FAQ
          </p>
          <h2 className="mb-14 text-center text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
            Common questions
          </h2>
          <div className="space-y-px bg-gray-100 dark:bg-gray-700">
            {faq.map((item) => (
              <details key={item.q} className="group bg-white dark:bg-gray-800">
                <summary className="flex cursor-pointer items-center justify-between px-6 py-5 text-[15px] font-medium text-gray-900 dark:text-white transition hover:text-gray-600 dark:hover:text-gray-300 [&::-webkit-details-marker]:hidden">
                  {item.q}
                  <ChevronDown className="h-4 w-4 flex-shrink-0 text-gray-300 dark:text-gray-600 transition-transform group-open:rotate-180" />
                </summary>
                <div className="px-6 pb-5">
                  <p className="text-sm leading-relaxed text-gray-500 dark:text-gray-400">{item.a}</p>
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA — exact Qelvra dark CTA */}
      <section className="bg-gray-900 px-6 py-24 text-white lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight lg:text-4xl">
            Your next clip is one download away.
          </h2>
          <p className="mt-4 text-[17px] text-gray-400 dark:text-gray-500">
            10 free clips. No card. No cloud. Just your computer.
          </p>
          <div className="mt-10">
            <button type="button" className="pearl-button" onClick={() => navigate('/auth?mode=signup')}>
              <div className="wrap">
                <p><span>✧</span><span>✦</span>Get CLPZ</p>
              </div>
            </button>
          </div>
        </div>
      </section>

      {/* Footer — exact Qelvra footer */}
      <footer className="border-t border-gray-100 dark:border-gray-800 px-6 py-14 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="grid grid-cols-1 gap-10 md:grid-cols-4">
            <div>
              <div className="flex items-center">
                <img src={logoUrl} alt="CLPZ" className="h-5 w-auto" />
              </div>
              <p className="mt-4 text-[13px] leading-relaxed text-gray-400 dark:text-gray-500">
                AI-powered clip generation that runs on your machine. No cloud. No subscription.
              </p>
            </div>
            <div>
              <h4 className="text-[13px] font-semibold text-gray-900 dark:text-white">Product</h4>
              <ul className="mt-4 space-y-2.5 text-[13px] text-gray-400 dark:text-gray-500">
                <li>How it Works</li>
                <li>Features</li>
                <li>FAQ</li>
              </ul>
            </div>
            <div>
              <h4 className="text-[13px] font-semibold text-gray-900 dark:text-white">Account</h4>
              <ul className="mt-4 space-y-2.5 text-[13px] text-gray-400 dark:text-gray-500">
                <li><a href="#faq" className="transition hover:text-gray-900 dark:hover:text-white">FAQ</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-[13px] font-semibold text-gray-900 dark:text-white">Get Started</h4>
              <ul className="mt-4 space-y-2.5 text-[13px] text-gray-400 dark:text-gray-500">
                <li><button onClick={() => navigate('/auth?mode=signup')} className="transition hover:text-gray-900 dark:hover:text-white">Create Account</button></li>
                <li><button onClick={() => navigate('/auth?mode=login')} className="transition hover:text-gray-900 dark:hover:text-white">Log In</button></li>
              </ul>
            </div>
          </div>
          <div className="mt-10 border-t border-gray-100 dark:border-gray-800 pt-8 text-center text-xs text-gray-300 dark:text-gray-600">
            © 2026 CLPZ. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
