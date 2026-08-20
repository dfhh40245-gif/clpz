"use client";

import { useEffect, useRef } from "react";
import { useEditor } from "@/editor/use-editor";
import { parseSubtitleFile } from "@/subtitles/parse";
import { insertCaptionChunksAsTextTrack } from "@/subtitles/insert";
import { processMediaAssets } from "@/media/processing";
import { AddMediaAssetCommand } from "@/commands/media";
import { InsertElementCommand } from "@/commands/timeline";
import { BatchCommand } from "@/commands";
import { buildElementFromMedia } from "@/timeline/element-utils";
import { mediaTimeFromSeconds } from "@/wasm";
import { DEFAULT_NEW_ELEMENT_DURATION } from "@/timeline/creation";

interface ClpzClip {
  index: number;
  title: string;
  url: string;
  duration: number;
}

/**
 * Listens for CLPZ-generated data via postMessage.
 *
 * Handles two message types:
 * 1. clpz-clips: Imports all generated clips as media assets into the editor
 * 2. clpz-captions: Parses ASS captions and inserts as editable text elements
 */
export function ClpzCaptionsListener() {
  const editor = useEditor();
  const hasReceivedClips = useRef(false);
  const hasReceivedCaptions = useRef(false);

  useEffect(() => {
    async function importClips(clips: ClpzClip[]) {
      const activeProject = editor.project.getActive();
      if (!activeProject) return;

      for (const clip of clips) {
        try {
          // Fetch the clip as a blob from CLPZ backend
          const response = await fetch(clip.url);
          if (!response.ok) continue;

          const blob = await response.blob();
          const file = new File([blob], `${clip.title}.mp4`, {
            type: "video/mp4",
          });

          // Process the file through OpenCut's media pipeline
          const processedAssets = await processMediaAssets({ files: [file] });
          if (processedAssets.length === 0) continue;

          const asset = processedAssets[0];
          const startTime = editor.playback.getCurrentTime();

          // Add the media asset
          const addMediaCmd = new AddMediaAssetCommand({
            projectId: activeProject.metadata.id,
            asset,
          });
          const assetId = addMediaCmd.getAssetId();

          const duration =
            asset.duration != null
              ? mediaTimeFromSeconds({ seconds: asset.duration })
              : DEFAULT_NEW_ELEMENT_DURATION;

          // Build and insert the element
          const element = buildElementFromMedia({
            mediaId: assetId,
            mediaType: "video",
            name: clip.title,
            duration,
            startTime,
          });

          const insertCmd = new InsertElementCommand({
            element,
            placement: { mode: "auto", trackType: "video" },
          });

          const batchCmd = new BatchCommand([addMediaCmd, insertCmd]);
          editor.command.execute({ command: batchCmd });
        } catch (err) {
          console.error(`[CLPZ] Failed to import clip ${clip.index}:`, err);
        }
      }
    }

    function handleMessage(event: MessageEvent) {
      const data = event.data;
      if (!data) return;

      // Handle clip imports
      if (data.type === "clpz-clips" && !hasReceivedClips.current) {
        const { clips } = data;
        if (Array.isArray(clips) && clips.length > 0) {
          hasReceivedClips.current = true;
          importClips(clips).catch((err) =>
            console.error("[CLPZ] Failed to import clips:", err)
          );
        }
      }

      // Handle caption imports
      if (data.type === "clpz-captions" && !hasReceivedCaptions.current) {
        const { assContent } = data;
        if (!assContent || typeof assContent !== "string") return;

        hasReceivedCaptions.current = true;

        try {
          const result = parseSubtitleFile({
            fileName: "clip_captions.ass",
            input: assContent,
          });

          if (result.captions.length === 0) return;

          insertCaptionChunksAsTextTrack({
            editor,
            captions: result.captions,
          });
        } catch (err) {
          console.error("[CLPZ] Failed to insert captions:", err);
        }
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [editor]);

  return null;
}
