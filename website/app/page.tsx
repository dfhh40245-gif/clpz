const features = [
  ["Context before keywords", "A sentence can sound punchy and still make no sense alone. CLPZ scores the setup, hook, payoff, and standalone clarity together."],
  ["An editor in the loop", "Every suggestion remains editable. Move the cut, fix a caption, change the crop, or restore the original without changing tools."],
  ["Local by design", "Video processing happens in the desktop app on your machine. The website handles the product, purchase, and trusted downloads."],
];

function Arrow() { return <span aria-hidden="true">↗</span>; }
function PearlLink({ href, children, small=false }: { href:string; children:React.ReactNode; small?:boolean }) {
  return <a className={`pearl-button${small?" pearl-button-small":""}`} href={href}><span className="pearl-wrap"><span className="pearl-label"><i>✧</i><i>✦</i>{children}</span></span></a>;
}

export default function Home() {
  return <main>
    <nav className="nav shell" aria-label="Primary navigation">
      <a className="brand" href="#top" aria-label="CLPZ home"><span className="brand-mark"><i>C</i></span><span>CLPZ</span></a>
      <div className="nav-links"><a href="#showcase">Showcase</a><a href="#inside">Inside CLPZ</a><a href="#get-clpz">Get CLPZ</a></div>
      <div className="nav-actions"><a href="/login">Sign in</a><a className="nav-download" href="/download">Download <Arrow /></a></div>
    </nav>

    <section className="hero shell" id="top">
      <div className="hero-copy">
        <p className="kicker"><span /> Desktop video studio</p>
        <h1>Find the clip<br />inside the video.</h1>
        <p className="lede">CLPZ watches the whole recording, surfaces the moments that stand alone, and gives you the final cut before you lose the idea.</p>
        <div className="hero-actions"><PearlLink href="/download">Download for Windows</PearlLink><a className="button quiet" href="#showcase">See it in action</a></div>
        <p className="availability"><span className="status-dot" /> Windows preview available · Mobile in development</p>
      </div>

      <div className="stage" aria-label="CLPZ desktop editor preview">
        <div className="stage-glow" />
        <div className="app-window">
          <div className="window-bar"><div className="window-brand"><span className="mini-mark">C</span> CLPZ</div><div className="window-status">Project / Episode 014</div><div className="window-dots"><i /><i /><i /></div></div>
          <div className="workspace">
            <aside className="rail" aria-hidden="true"><b>+</b><span>⌁</span><span>◫</span><span>CC</span><span>↗</span></aside>
            <div className="preview-pane"><div className="preview-label">PREVIEW · 00:42</div><div className="portrait-frame"><div className="speaker-shape" /><p>the part nobody tells you <em>before</em> you start</p></div><div className="transport"><span>00:17.8</span><b>▶</b><span>00:42.1</span></div></div>
            <div className="moments-pane"><div className="pane-head"><span>FOUND MOMENTS</span><b>6</b></div>
              <article className="moment selected"><strong>01</strong><div><b>The mistake that changed the launch</b><small>00:14 — 00:56</small></div><mark>9.2</mark></article>
              <article className="moment"><strong>02</strong><div><b>What we learned in week one</b><small>04:18 — 05:02</small></div><mark>8.7</mark></article>
              <article className="moment"><strong>03</strong><div><b>The advice we ignored</b><small>09:31 — 10:04</small></div><mark>8.1</mark></article>
              <div className="analysis"><span>Context</span><span>Hook</span><span>Payoff</span></div>
            </div>
          </div>
          <div className="timeline"><div className="timecode"><span>00:00</span><span>00:15</span><span>00:30</span><span>00:45</span></div><div className="track">{Array.from({length:12}).map((_,i)=><i key={i}/>)}</div><div className="caption-track"><b>the part</b><b>nobody</b><b>tells you</b><b className="active">before</b><b>you start</b></div><div className="playhead" /></div>
        </div>
        <div className="score-float"><small>STANDALONE SCORE</small><strong>9.2</strong><span>Ready to refine</span></div>
      </div>
    </section>

    <section className="manifesto shell"><p className="section-index">01 / THE DIFFERENCE</p><p className="manifesto-copy">Most clip tools search for loud words. <strong>CLPZ looks for complete ideas.</strong> It keeps the setup and payoff together, then puts the decision back in your hands.</p></section>

    <section className="showcase shell" id="showcase">
      <header className="section-heading showcase-heading"><div><p className="section-index">02 / PRODUCT SHOWCASE</p><h2>From full episode<br />to finished short.</h2></div><p>Drop in one source. CLPZ finds complete moments, opens them in a real editor, and keeps every decision reversible.</p></header>

      <article className="showcase-row">
        <div className="showcase-copy"><span className="showcase-number">01</span><p className="section-index">MOMENT DETECTION</p><h3>It reads for the whole idea.</h3><p>CLPZ checks context, completeness, hook strength, payoff, emotional intensity, and whether the moment makes sense without the rest of the video.</p><div className="tag-cloud"><span>Context</span><span>Hook strength</span><span>Payoff</span><span>Standalone clarity</span></div></div>
        <div className="score-board"><div className="score-head"><div><b>“the moment everything clicked”</b><small>24:41 — 25:23 · 0:42</small></div><strong>9.4</strong></div>{[["Hook","88%","8.8"],["Context","94%","9.4"],["Completeness","97%","9.7"],["Payoff","91%","9.1"]].map(([label,width,value])=><div className="metric" key={label}><span>{label}</span><div><i style={{width}}/></div><b>{value}</b></div>)}<small className="score-note">Illustrative analysis</small></div>
      </article>

      <article className="showcase-row reverse">
        <div className="editor-board"><div className="editor-tools"><b>Trim</b><span>Split</span><span>Text</span><span>Audio</span><span>Crop</span><span>Speed</span></div><div className="editor-screen"><div className="edit-frame"><span>PREVIEW</span><p>one choice changed<br /><em>everything</em></p></div></div><div className="editor-timeline">{["VIDEO","CAPTIONS","TEXT","AUDIO"].map((label,index)=><div key={label}><span>{label}</span><i className={`lane lane-${index}`}/></div>)}<b className="editor-playhead"/></div></div>
        <div className="showcase-copy"><span className="showcase-number">02</span><p className="section-index">EDITOR</p><h3>Finish without changing apps.</h3><p>Trim and split on the timeline, edit captions word by word, add text, adjust audio and speed, then fix the vertical crop. Undo and redo work the way you expect.</p><ul className="check-list"><li>Word-level caption editing</li><li>Text and overlay positioning</li><li>9:16 crop with live preview</li></ul></div>
      </article>

      <article className="showcase-row">
        <div className="showcase-copy"><span className="showcase-number">03</span><p className="section-index">HOOKS + BATCH</p><h3>Sharpen the opening. Keep the meaning.</h3><p>CLPZ can pull a stronger opening from the same clip, then process the rest of the episode while showing the real stage for every candidate.</p><div className="hook-compare"><div><small>ORIGINAL</small><p>“So, today I kind of wanted to talk about…”</p></div><div><small>SUGGESTED</small><p>“Nobody tells you this before you start.”</p></div></div></div>
        <div className="batch-board">{[["01","Complete","0:58"],["02","Complete","1:04"],["03","Rendering","0:41"],["04","Transcribing","0:12"]].map(([num,state,time],index)=><div className="batch-item" key={num}><div className={`batch-thumb batch-${index}`}><span>CLIP {num}</span></div><p className={state==="Complete"?"done":"working"}>{state==="Complete"?"✓ ":"• "}{state}</p><small>{time}</small></div>)}</div>
      </article>
    </section>

    <section className="inside" id="inside"><div className="shell">
      <header className="section-heading split-heading"><div><p className="section-index">03 / INSIDE CLPZ</p><h2>The cut stays<br />under your control.</h2></div><p>Fast where automation helps. Precise where your taste matters.</p></header>
      <div className="feature-list">{features.map(([title,copy],index)=><article className="feature" key={title}><span>0{index+1}</span><h3>{title}</h3><p>{copy}</p></article>)}</div>
      <div className="proof-grid"><div className="vertical-proof"><div className="safe-zone"><small>9:16 SAFE AREA</small><p>captions that stay<br /><em>inside</em> the frame</p></div></div><div className="proof-copy"><p className="section-index">CAPTIONS + REFRAMING</p><h3>Built for vertical<br />from the first cut.</h3><p>Word-timed captions, centered subjects, and platform-safe layouts are ready before export. You can still move every element.</p><ul><li>Editable word timing</li><li>Automatic 9:16 crop</li><li>Preview before rendering</li></ul></div></div>
    </div></section>

    <section className="get shell" id="get-clpz"><div className="get-card"><div><p className="section-index">04 / GET CLPZ</p><h2>Your footage stays local.<br />Your purchase stays simple.</h2><p>Purchase securely through Gumroad, keep the receipt in your inbox, and download the Windows app from a versioned release.</p></div><div className="purchase"><span className="purchase-label">DESKTOP LICENSE</span><strong>Available on Gumroad</strong><PearlLink href="/buy" small>Buy CLPZ</PearlLink><a className="text-link" href="/download">Already have it? Download the app →</a></div></div></section>

    <footer className="footer shell"><a className="brand" href="#top"><span className="brand-mark"><i>C</i></span><span>CLPZ</span></a><p>Turn long video into the short worth watching.</p><div><a href="/privacy">Privacy</a><a href="/terms">Terms</a><span>© 2026 CLPZ</span></div></footer>
  </main>;
}
