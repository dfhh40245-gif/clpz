import { AnimatedGradient } from "@/components/animated-gradient";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { NavAuth } from "@/components/nav-auth";

const features = [
  ["Context before keywords", "A sentence can sound punchy and still make no sense alone. CLPZ reads the transcript for complete ideas, not just punchy lines."],
  ["An editor in the loop", "Every suggestion remains editable. Move the cut, fix a caption, change the crop, or restore the original without changing tools."],
  ["Local by design", "Video processing happens in the desktop app on your machine. The website handles the product, purchase, and trusted downloads."],
];

function Arrow() { return <span aria-hidden="true">↗</span>; }
function PearlLink({ href, children, small=false }: { href:string; children:React.ReactNode; small?:boolean }) {
  return <a className={`pearl-button${small?" pearl-button-small":""}`} href={href}><span className="pearl-wrap"><span className="pearl-label"><i>✧</i><i>✦</i>{children}</span></span></a>;
}

export default function Home() {
  return <main id="main-content">
    <nav className="nav shell" aria-label="Primary navigation">
      <Brand href="#top" />
      <div className="nav-links"><a href="#showcase">Showcase</a><a href="#inside">Inside CLPZ</a><a href="#get-clpz">Get CLPZ</a></div>
      <div className="nav-actions"><ThemeToggle /><NavAuth /><a className="nav-download" href="/download">Download <Arrow /></a></div>
    </nav>

    <section className="hero shell" id="top">
      <AnimatedGradient className="hero-gradient" />
      <div className="hero-copy">
        <p className="kicker"><span /> Desktop video studio</p>
        <h1>Find the clip<br />inside the video.</h1>
        <p className="lede">CLPZ watches the whole recording, surfaces the moments that stand alone, and gives you the final cut before you lose the idea.</p>
        <div className="hero-actions"><PearlLink href="/download">Download for Windows</PearlLink><a className="button quiet" href="#showcase">See it in action</a></div>
        <p className="availability"><span className="status-dot" /> Windows preview available · <a href="/download/android">Download Android APK</a></p>
      </div>

      <div className="stage" aria-label="CLPZ desktop editor preview">
        <div className="stage-glow" />
        <div className="app-window">
          <div className="window-bar"><div className="window-brand"><span className="mini-mark">C</span> CLPZ</div><div className="window-status">Project / Episode 014</div><div className="window-dots"><i /><i /><i /></div></div>
          <div className="workspace">
            <aside className="rail" aria-hidden="true"><b>+</b><span>⌁</span><span>◫</span><span>CC</span><span>↗</span></aside>
            <div className="preview-pane"><div className="preview-label">PREVIEW · 00:42</div><div className="portrait-frame"><div className="speaker-shape" /><p>the part nobody tells you <em>before</em> you start</p></div><div className="transport"><span>00:17.8</span><b>▶</b><span>00:42.1</span></div></div>
            <div className="moments-pane"><div className="pane-head"><span>FOUND MOMENTS</span><b>6</b></div>
              <article className="moment selected"><strong>01</strong><div><b>The mistake that changed the launch</b><small>00:14 — 00:56</small></div></article>
              <article className="moment"><strong>02</strong><div><b>What we learned in week one</b><small>04:18 — 05:02</small></div></article>
              <article className="moment"><strong>03</strong><div><b>The advice we ignored</b><small>09:31 — 10:04</small></div></article>
              <div className="analysis"><span>Context</span><span>Clarity</span><span>Payoff</span></div>
            </div>
          </div>
          <div className="timeline"><div className="timecode"><span>00:00</span><span>00:15</span><span>00:30</span><span>00:45</span></div><div className="track">{Array.from({length:12}).map((_,i)=><i key={i}/>)}</div><div className="caption-track"><b>the part</b><b>nobody</b><b>tells you</b><b className="active">before</b><b>you start</b></div><div className="playhead" /></div>
        </div>
      </div>
    </section>

    <section className="manifesto shell"><p className="section-index">01 / THE DIFFERENCE</p><p className="manifesto-copy">Most clip tools search for loud words. <strong>CLPZ looks for complete ideas.</strong> It keeps the setup and payoff together, then puts the decision back in your hands.</p></section>

    <section className="showcase shell" id="showcase">
      <header className="section-heading showcase-heading"><div><p className="section-index">02 / PRODUCT SHOWCASE</p><h2>From full episode<br />to finished short.</h2></div><p>Drop in one source. CLPZ finds complete moments, opens them in a real editor, and keeps every decision reversible.</p></header>

      <article className="showcase-row">
        <div className="showcase-copy"><span className="showcase-number">01</span><p className="section-index">MOMENT DETECTION</p><h3>It reads for the whole idea.</h3><p>CLPZ checks context, completeness, pacing, and whether the moment makes sense without the rest of the video.</p><div className="tag-cloud"><span>Context</span><span>Clarity</span><span>Payoff</span><span>Standalone clarity</span></div></div>
        <div className="score-board"><div className="score-head"><div><b>“the moment everything clicked”</b><small>24:41 — 25:23 · 0:42</small></div><span className="score-flag">Ready to refine</span></div><ul className="quality-list">{["Trims to a complete idea","Captions carried over exactly","Vertical crop keeps both speakers in frame","Audio normalized for short-form"].map(item=><li key={item}><span>✓</span>{item}</li>)}</ul><small className="score-note">Automatic pipeline checks</small></div>
      </article>

      <article className="showcase-row reverse">
        <div className="editor-board"><div className="editor-tools"><b>Trim</b><span>Split</span><span>Text</span><span>Audio</span><span>Crop</span><span>Speed</span></div><div className="editor-screen"><div className="edit-frame"><span>PREVIEW</span><p>one choice changed<br /><em>everything</em></p></div></div><div className="editor-timeline">{["VIDEO","CAPTIONS","TEXT","AUDIO"].map((label,index)=><div key={label}><span>{label}</span><i className={`lane lane-${index}`}/></div>)}<b className="editor-playhead"/></div></div>
        <div className="showcase-copy"><span className="showcase-number">02</span><p className="section-index">EDITOR</p><h3>Finish without changing apps.</h3><p>Trim and split on the timeline, edit captions word by word, add text, adjust audio and speed, then fix the vertical crop. Undo and redo work the way you expect.</p><ul className="check-list"><li>Word-level caption editing</li><li>Text and overlay positioning</li><li>9:16 crop with live preview</li></ul></div>
      </article>

      <article className="showcase-row">
        <div className="showcase-copy"><span className="showcase-number">03</span><p className="section-index">BATCH PROCESSING</p><h3>Queue the episode. Keep working.</h3><p>Send the rest of the episode through the pipeline and watch every candidate move through real stages — transcription, analysis, rendering — as each clip finishes.</p></div>
        <div className="batch-board">{[["01","Complete","0:58"],["02","Complete","1:04"],["03","Rendering","0:41"],["04","Transcribing","0:12"]].map(([num,state,time],index)=><div className="batch-item" key={num}><div className={`batch-thumb batch-${index}`}><span>CLIP {num}</span></div><p className={state==="Complete"?"done":"working"}>{state==="Complete"?"✓ ":"• "}{state}</p><small>{time}</small></div>)}</div>
      </article>
    </section>

    <section className="inside" id="inside"><div className="shell">
      <header className="section-heading split-heading"><div><p className="section-index">03 / INSIDE CLPZ</p><h2>The cut stays<br />under your control.</h2></div><p>Fast where automation helps. Precise where your taste matters.</p></header>
      <div className="feature-list">{features.map(([title,copy],index)=><article className="feature" key={title}><span>0{index+1}</span><h3>{title}</h3><p>{copy}</p></article>)}</div>
      <div className="proof-grid"><div className="vertical-proof"><div className="safe-zone"><small>9:16 SAFE AREA</small><p>captions that stay<br /><em>inside</em> the frame</p></div></div><div className="proof-copy"><p className="section-index">CAPTIONS + REFRAMING</p><h3>Built for vertical<br />from the first cut.</h3><p>Word-timed captions, centered subjects, and platform-safe layouts are ready before export. You can still move every element.</p><ul><li>Editable word timing</li><li>Automatic 9:16 crop</li><li>Preview before rendering</li></ul></div></div>
    </div></section>

    <section className="get shell" id="get-clpz"><header className="pricing-heading"><p className="section-index">04 / GET CLPZ</p><h2>Start small. Scale when<br />the clips start moving.</h2><p>Credits are used for AI analysis. Editing and local exports stay available in the desktop and mobile apps.</p></header><div className="pricing-grid"><article className="price-card featured"><span className="price-badge">BEST VALUE</span><p>CREATOR</p><h3><strong>$7</strong> / month</h3><ul><li>120 AI credits each month</li><li>Desktop and mobile editors</li><li>Unused credits roll for 60 days</li></ul><a className="checkout-button" href="/buy?plan=creator">View Creator plan →</a></article><article className="price-card"><p>50-CREDIT PACK</p><h3><strong>$4</strong> once</h3><ul><li>No subscription required</li><li>Credits never expire</li><li>Use with any CLPZ account</li></ul><a className="checkout-button secondary" href="/buy?plan=credits-50">View 50-credit pack →</a></article><article className="price-card"><p>200-CREDIT PACK</p><h3><strong>$11</strong> once</h3><ul><li>Best for larger projects</li><li>Credits never expire</li><li>Use with any CLPZ account</li></ul><a className="checkout-button secondary" href="/buy?plan=credits-200">View 200-credit pack →</a></article></div><div className="app-downloads"><a href="/download">Download Windows app</a><a href="/download/android">Download Android APK</a></div><p className="pricing-footnote">Credit plans are coming soon; checkout is not open yet. Sign in with the same account on the website, Windows app, and Android app.</p></section>

    <footer className="footer shell"><Brand href="#top" /><p>Turn long video into the short worth watching.</p><div><a href="/privacy">Privacy</a><a href="/terms">Terms</a><span>© 2026 CLPZ</span></div></footer>
  </main>;
}
