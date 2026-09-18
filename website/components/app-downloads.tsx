import { WindowsMark, AndroidMark } from "./platform-marks";

export function AppDownloads() {
  return <div className="platform-grid">
    <article className="platform-card">
      <div className="platform-top"><WindowsMark /><span className="release-tag">Desktop studio</span></div>
      <h3>A little more room.<br />A lot more control.</h3>
      <p>Find moments in long recordings, refine captions, and finish your clips on Windows.</p>
      <ul><li>Local video processing</li><li>Timeline, text, audio & speed tools</li><li>Original footage stays untouched</li></ul>
      <a href="/download" className="download-action">Download for Windows <span aria-hidden="true">↓</span></a>
      <small>Windows 10 / 11 · 64-bit installer</small>
    </article>
    <article className="platform-card mobile-platform">
      <div className="platform-top"><AndroidMark /><span className="release-tag">Pocket studio</span></div>
      <h3>Your next great clip.<br />Anywhere you are.</h3>
      <p>Bring in a video, shape the cut, add your words, and take it straight to your favorite app.</p>
      <ul><li>Saved drafts you can return to</li><li>Vertical, square & landscape formats</li><li>Render, save & share on your phone</li></ul>
      <a href="/download/android" className="download-action">Download Android APK <span aria-hidden="true">↓</span></a>
      <small>Android 8 or later · Preview release</small>
    </article>
  </div>;
}
