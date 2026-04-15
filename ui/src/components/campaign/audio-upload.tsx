/**
 * Audio file upload (Phase 2 A.1).
 *
 * Dashed-border dropzone with MiroFish teal accent — signals that audio
 * feeds both TRIBE v2 (neural) and MiroFish (social simulation). Supports
 * drag-and-drop and click-to-browse.
 *
 * Validation (all client-side, before any upload attempt):
 *   1. File extension — .wav / .mp3 / .flac / .ogg only
 *   2. File size    — < 10 MB
 *   3. Duration     — < 60 s (decoded via Web Audio API — metadata is
 *                     unreliable for .flac / .ogg so we decode the PCM).
 *
 * Error messages surface inline below the dropzone AND via a toast so the
 * reviewer can spot them in either context.
 */

import { useCallback, useRef, useState } from 'react';
import { toast } from 'sonner';
import { FileAudio, UploadCloud, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const MAX_BYTES = 10 * 1024 * 1024; // 10 MB
const MAX_DURATION_SECONDS = 60;
const ALLOWED_EXTENSIONS = ['wav', 'mp3', 'flac', 'ogg'] as const;

// Exact message required by Track A.1 spec.
const DURATION_ERROR =
  'Audio must be under 60 seconds for laptop-class inference. Longer files supported on cloud hardware.';

export interface AudioFileInfo {
  file: File;
  durationSeconds: number;
}

export interface AudioUploadProps {
  value: AudioFileInfo | null;
  onChange: (info: AudioFileInfo | null) => void;
  disabled?: boolean;
}

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf('.');
  if (dot === -1) return '';
  return filename.slice(dot + 1).toLowerCase();
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

/**
 * Decode audio with the Web Audio API to get an accurate duration.
 * Container metadata is unreliable across .flac / .ogg, so we decode PCM.
 */
async function detectAudioDuration(file: File): Promise<number> {
  // Lazily construct the context — some browsers gate it until first use.
  // Use webkit-prefixed fallback for older Safari builds.
  type AudioContextCtor = typeof AudioContext;
  const AC: AudioContextCtor | undefined =
    (window as unknown as { AudioContext?: AudioContextCtor }).AudioContext ??
    (window as unknown as { webkitAudioContext?: AudioContextCtor })
      .webkitAudioContext;

  if (!AC) {
    throw new Error('Web Audio API unavailable in this browser');
  }

  const ctx = new AC();
  try {
    const buf = await file.arrayBuffer();
    // decodeAudioData mutates the buffer on some engines — pass a copy.
    const copy = buf.slice(0);
    const audioBuf = await ctx.decodeAudioData(copy);
    return audioBuf.duration;
  } finally {
    // Release the AudioContext eagerly — we only needed it for decoding.
    void ctx.close().catch(() => {});
  }
}

export function AudioUpload({ value, onChange, disabled }: AudioUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [validating, setValidating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const validateAndAccept = useCallback(
    async (file: File) => {
      setErrorMsg(null);
      setValidating(true);
      try {
        // 1. Extension check
        const ext = getExtension(file.name);
        if (!ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number])) {
          const msg = `Unsupported format .${ext || '(none)'}. Use ${ALLOWED_EXTENSIONS.map((e) => '.' + e).join(', ')}.`;
          setErrorMsg(msg);
          toast.error(msg);
          return;
        }

        // 2. Size check
        if (file.size > MAX_BYTES) {
          const msg = `File too large (${formatBytes(file.size)}). Maximum 10 MB.`;
          setErrorMsg(msg);
          toast.error(msg);
          return;
        }

        // 3. Duration check (decode PCM — metadata is unreliable)
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

        if (duration > MAX_DURATION_SECONDS) {
          setErrorMsg(DURATION_ERROR);
          toast.error(DURATION_ERROR);
          return;
        }

        onChange({ file, durationSeconds: duration });
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
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3 rounded-md border border-mirofish/40 bg-mirofish-muted px-3 py-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <FileAudio className="size-4 shrink-0 text-mirofish" />
            <div className="flex min-w-0 flex-col">
              <span className="truncate font-mono text-[0.78rem] text-foreground">
                {value.file.name}
              </span>
              <span className="font-mono text-[0.62rem] text-muted-foreground tabular-nums">
                {formatDuration(value.durationSeconds)} · {formatBytes(value.file.size)}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClear}
            disabled={disabled}
            className="flex size-6 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-foreground/[0.06] hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
            aria-label="Remove audio file"
          >
            <X className="size-3.5" />
          </button>
        </div>
        <p className="font-mono text-[0.6rem] text-mirofish/80">
          Audio will be routed to TRIBE v2 and transcribed for MiroFish agents.
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
              ? 'Reading audio…'
              : dragActive
                ? 'Drop to upload'
                : 'Drop audio file here, or click to browse'}
          </span>
          <span className="font-mono text-[0.6rem] tracking-[0.08em] text-muted-foreground uppercase">
            wav · mp3 · flac · ogg · max 10 MB · ≤ 60 s
          </span>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".wav,.mp3,.flac,.ogg,audio/wav,audio/mpeg,audio/flac,audio/ogg"
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
