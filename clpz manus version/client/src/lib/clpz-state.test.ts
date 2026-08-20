import { describe, expect, it } from "vitest";
import { humanFileSize, isYouTubeUrl, processingStages } from "./clpz-state";

describe("CLPZ UI state helpers", () => {
  it("accepts common YouTube URL shapes and rejects unrelated links", () => {
    expect(isYouTubeUrl("https://www.youtube.com/watch?v=clipz")).toBe(true);
    expect(isYouTubeUrl("https://youtu.be/clipz")).toBe(true);
    expect(isYouTubeUrl("https://example.com/watch?v=clipz")).toBe(false);
    expect(isYouTubeUrl("not a URL")).toBe(false);
  });

  it("formats file sizes for the selected-file UI", () => {
    expect(humanFileSize(1024 * 700)).toBe("700 KB");
    expect(humanFileSize(1024 * 1024 * 24.36)).toBe("24.4 MB");
  });

  it("keeps the UI processing flow in its required sequential order", () => {
    expect(processingStages).toEqual(["Download", "Transcription", "Analysis", "Clip selection", "Rendering"]);
  });
});
