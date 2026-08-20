export const processingStages = ["Download", "Transcription", "Analysis", "Clip selection", "Rendering"] as const;

export type ProcessingStage = (typeof processingStages)[number];

export function isYouTubeUrl(value: string) {
  try {
    const url = new URL(value.trim());
    return ["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"].includes(url.hostname);
  } catch {
    return false;
  }
}

export function humanFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
