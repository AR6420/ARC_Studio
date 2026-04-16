/**
 * Media file upload — audio (Phase 2 A.1) and video (Phase 2 A.2).
 *
 * Single dropzone that detects audio vs video by extension and applies the
 * appropriate validation:
 *
 *   Audio: .wav/.mp3/.flac/.ogg, ≤ 10 MB, ≤ 60 s
 *          duration is decoded via the Web Audio API (PCM-accurate).
 *   Video: .mp4/.webm/.mov, ≤ 25 MB, ≤ 15 s, ≤ 720 p height
 *          duration + dimensions read from a hidden <video> element.
 *
 * Selected state shows file metadata. For video, a thumbnail extracted from
 * the first frame is displayed alongside the metadata.
 *
 * Error messages surface inline below the dropzone AND via a toast.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { FileAudio, FileVideo, UploadCloud, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Limits (kept in sync with orchestrator/config.py) ────────────────────────
const AUDIO_MAX_BYTES = 10 * 1024 * 1024;
const AUDIO_MAX_DURATION_SECONDS = 60;
const AUDIO_EXTENSIONS = ['wav', 'mp3', 'flac', 'ogg'] as const;

const VIDEO_MAX_BYTES = 25 * 1024 * 1024;
const VIDEO_MAX_DURATION_SECONDS = 15;
const VIDEO_MAX_RESOLUTION_HEIGHT = 720;
const VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov'] as const;

// Exact messages required by Track A.1 / A.2 spec.
const AUDIO_DURATION_ERROR =
  'Audio must be under 60 seconds for laptop-class inference. Longer files supported on cloud hardware.';
const VIDEO_DURATION_ERROR =
  'Video must be under 15 seconds for laptop-class inference.';

export type MediaType = 'audio' | 'video';

export interface MediaFileInfo {
  file: File;
  mediaType: MediaType;
  durationSeconds: number;
  // Populated for video only; undefined for audio.
  width?: number;
  height?: number;
  thumbnailUrl?: string;
}

export interface MediaUploadProps {
  value: MediaFileInfo | null;
  onChange: (info: MediaFileInfo | null) => void;
  disabled?: boolean;
}

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf('.');
  if (dot === -1) return '';
  return filename.slice(dot + 1).toLowerCase();
}

function classifyExtension(ext: string): MediaType | null {
  if ((AUDIO_EXTENSIONS as readonly string[]).includes(ext)) return 'audio';
  if ((VIDEO_EXTENSIONS as readonly string[]).includes(ext)) return 'video';
  return null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = seconds - mins * 60;
  return `${mins}:${secs.toFixed(1).padStart(4, '0')}`;
}

/** Decode audio PCM with Web Audio API to get an accurate duration. */
async function detectAudioDuration(file: File): Promise<number> {
  type AudioContextCtor = typeof AudioContext;
  const AC: AudioContextCtor | undefined =
    (window as unknown as { AudioContext?: AudioContextCtor }).AudioContext ??
    (window as unknown as { webkitAudioContext?: AudioContextCtor })
      .webkitAudioContext;
  if (!AC) throw new Error('Web Audio API unavailable in this browser');

  const ctx = new AC();
  try {
    const buf = await file.arrayBuffer();
    // decodeAudioData mutates the buffer on some engines — pass a copy.
    const copy = buf.slice(0);
    const audioBuf = await ctx.decodeAudioData(copy);
    return audioBuf.duration;
  } finally {
    void ctx.close().catch(() => {});
  }
}

/** Read video metadata + extract first-frame thumbnail via a hidden element. */
interface VideoMeta {
  duration: number;
  width: number;
  height: number;
  thumbnailUrl: string;
}

async function detectVideoMetadata(file: File): Promise<VideoMeta> {
  const objectUrl = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.preload = 'metadata';
  video.muted = true;
  // Required for inline frame seeking in some browsers.
  video.playsInline = true;
  video.src = objectUrl;

  try {
    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () =>
        reject(new Error('Could not decode video file (codec not supported?)'));
    });
    const duration = video.duration;
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!Number.isFinite(duration) || duration <= 0) {
      throw new Error('Video has no duration metadata');
    }
    if (width <= 0 || height <= 0) {
      throw new Error('Video has no width/height metadata');
    }

    // Seek to ~10% to grab a representative thumbnail.
    await new Promise<void>((resolve, reject) => {
      video.onseeked = () => resolve();
      video.onerror = () => reject(new Error('Video seek failed'));
      video.currentTime = Math.min(0.1 * duration, 0.5);
    });

    const canvas = document.createElement('canvas');
    // Cap thumbnail width at 320 to keep the data URL light.
    const targetWidth = Math.min(320, width);
    const targetHeight = Math.round(targetWidth * (height / width));
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const ctx2d = canvas.getContext('2d');
    if (!ctx2d) throw new Error('Canvas 2D context unavailable');
    ctx2d.drawImage(video, 0, 0, targetWidth, targetHeight);
    const thumbnailUrl = canvas.toDataURL('image/jpeg', 0.78);

    return { duration, width, height, thumbnailUrl };
  } finally {
    // Note: caller owns the objectUrl until they replace the file. We free it
    // on unmount via the useEffect cleanup in the component.
    URL.revokeObjectURL(objectUrl);
  }
}

export function MediaUpload({ value, onChange, disabled }: MediaUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [validating, setValidating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Free the object URL behind the thumbnail when the selected file changes.
  useEffect(() => {
    return () => {
      if (value?.thumbnailUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(value.thumbnailUrl);
      }
    };
  }, [value]);

  const validateAndAccept = useCallback(
    async (file: File) => {
      setErrorMsg(null);
      setValidating(true);
      try {
        const ext = getExtension(file.name);
        const mediaType = classifyExtension(ext);

        if (mediaType === null) {
          const allowed = [
            ...AUDIO_EXTENSIONS.map((e) => '.' + e),
            ...VIDEO_EXTENSIONS.map((e) => '.' + e),
          ].join(', ');
          const msg = `Unsupported format .${ext || '(none)'}. Use ${allowed}.`;
          setErrorMsg(msg);
          toast.error(msg);
          return;
        }

        if (mediaType === 'audio') {
          if (file.size > AUDIO_MAX_BYTES) {
            const msg = `Audio file too large (${formatBytes(file.size)}). Maximum 10 MB.`;
            setErrorMsg(msg);
            toast.error(msg);
            return;
          }
          let duration: number;
          try {
            duration = await detectAudioDuration(file);
          } catch (err) {
            const msg =
              err instanceof Error
                ? `Could not decode audio: ${err.message}`
                : 'Could not decode audio file.';
            setErrorMsg(msg);
            toast.error(msg);
            return;
          }
          if (duration > AUDIO_MAX_DURATION_SECONDS) {
            setErrorMsg(AUDIO_DURATION_ERROR);
            toast.error(AUDIO_DURATION_ERROR);
            return;
          }
          onChange({ file, mediaType: 'audio', durationSeconds: duration });
          return;
        }

        // Video branch
        if (file.size > VIDEO_MAX_BYTES) {
          const msg = `Video file too large (${formatBytes(file.size)}). Maximum 25 MB.`;
          setErrorMsg(msg);
          toast.error(msg);
          return;
        }
        let meta: VideoMeta;
        try {
          meta = await detectVideoMetadata(file);
        } catch (err) {
          const msg =
            err instanceof Error
              ? `Could not decode video: ${err.message}`
              : 'Could not decode video file.';
          setErrorMsg(msg);
          toast.error(msg);
          return;
        }
        if (meta.duration > VIDEO_MAX_DURATION_SECONDS) {
          setErrorMsg(VIDEO_DURATION_ERROR);
          toast.error(VIDEO_DURATION_ERROR);
          return;
        }
        if (meta.height > VIDEO_MAX_RESOLUTION_HEIGHT) {
          // Don't reject — backend will downscale via ffmpeg. Surface a hint.
          toast.message(
            `Video is ${meta.width}×${meta.height}; the server will downscale to ${VIDEO_MAX_RESOLUTION_HEIGHT}p before scoring.`,
          );
        }
        onChange({
          file,
          mediaType: 'video',
          durationSeconds: meta.duration,
          width: meta.width,
          height: meta.height,
          thumbnailUrl: meta.thumbnailUrl,
        });
      } finally {
        setValidating(false);
      }
    },
    [onChange],
  );

  function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    void validateAndAccept(files[0]);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (disabled) return;
    handleFiles(e.dataTransfer.files);
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    setDragActive(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }

  function handleBrowseClick() {
    if (disabled) return;
    inputRef.current?.click();
  }

  function handleClear(e: React.MouseEvent) {
    e.stopPropagation();
    setErrorMsg(null);
    onChange(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  // ── Selected state: compact summary with clear button ─────────────────
  if (value) {
    const Icon = value.mediaType === 'video' ? FileVideo : FileAudio;
    const dimensionsLabel =
      value.mediaType === 'video' && value.width && value.height
        ? ` · ${value.width}×${value.height}`
        : '';
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 rounded-md border border-mirofish/40 bg-mirofish-muted px-3 py-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            {value.mediaType === 'video' && value.thumbnailUrl ? (
              <img
                src={value.thumbnailUrl}
                alt=""
                className="h-10 w-[60px] shrink-0 rounded-sm border border-mirofish/30 object-cover"
              />
            ) : (
              <Icon className="size-4 shrink-0 text-mirofish" />
            )}
            <div className="flex min-w-0 flex-col">
              <span className="truncate font-mono text-[0.78rem] text-foreground">
                {value.file.name}
              </span>
              <span className="font-mono text-[0.62rem] text-muted-foreground tabular-nums">
                {formatDuration(value.durationSeconds)} · {formatBytes(value.file.size)}
                {dimensionsLabel}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClear}
            disabled={disabled}
            className="flex size-6 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-foreground/[0.06] hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
            aria-label={`Remove ${value.mediaType} file`}
          >
            <X className="size-3.5" />
          </button>
        </div>
        <p className="font-mono text-[0.6rem] text-mirofish/80">
          {value.mediaType === 'video'
            ? 'Video will be routed to TRIBE v2 V-JEPA2 (frames) + Wav2Vec-BERT (extracted audio).'
            : 'Audio will be routed to TRIBE v2 and transcribed for MiroFish agents.'}
        </p>
      </div>
    );
  }

  // ── Empty state: dashed dropzone with teal accent ─────────────────────
  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={handleBrowseClick}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleBrowseClick();
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        aria-disabled={disabled}
        className={cn(
          'group relative flex flex-col items-center justify-center gap-2 rounded-md border border-dashed px-4 py-6 text-center transition-colors duration-150',
          'cursor-pointer outline-none',
          'focus-visible:ring-1 focus-visible:ring-mirofish/60',
          dragActive
            ? 'border-mirofish bg-mirofish-muted'
            : 'border-mirofish/40 bg-sidebar hover:border-mirofish/70 hover:bg-mirofish-muted/50',
          disabled && 'pointer-events-none opacity-50',
          errorMsg && !dragActive && 'border-destructive/50',
        )}
      >
        {validating ? (
          <Loader2 className="size-4 animate-spin text-mirofish" />
        ) : (
          <UploadCloud className="size-4 text-mirofish" />
        )}
        <div className="flex flex-col gap-0.5">
          <span className="text-[0.82rem] text-foreground/90">
            {validating
              ? 'Reading file…'
              : dragActive
                ? 'Drop to upload'
                : 'Drop audio or video here, or click to browse'}
          </span>
          <span className="font-mono text-[0.6rem] tracking-[0.08em] text-muted-foreground uppercase">
            audio: wav · mp3 · flac · ogg · ≤ 10 MB · ≤ 60 s
          </span>
          <span className="font-mono text-[0.6rem] tracking-[0.08em] text-muted-foreground uppercase">
            video: mp4 · webm · mov · ≤ 25 MB · ≤ 15 s · ≤ 720 p
          </span>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".wav,.mp3,.flac,.ogg,.mp4,.webm,.mov,audio/wav,audio/mpeg,audio/flac,audio/ogg,video/mp4,video/webm,video/quicktime"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
          disabled={disabled}
        />
      </div>
      {errorMsg && (
        <p
          role="alert"
          className="font-mono text-[0.68rem] leading-snug text-destructive"
        >
          {errorMsg}
        </p>
      )}
    </div>
  );
}
