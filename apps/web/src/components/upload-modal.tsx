'use client';

import { useCallback, useRef, useState } from 'react';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  onUpload: (file: File) => void;
}

const ACCEPTED = 'image/png,image/jpeg,image/webp';
const MAX_MB = 25;

export function UploadModal({ open, onClose, onUpload }: UploadModalProps) {
  const [preview, setPreview] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = useCallback((f: File) => {
    if (!ACCEPTED.split(',').includes(f.type)) {
      setError('Unsupported file type. Please use PNG, JPG/JPEG, or WebP.');
      return false;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File is over ${MAX_MB}MB. Please choose a smaller image.`);
      return false;
    }
    setError(null);
    return true;
  }, []);

  const pick = useCallback(
    (f: File | undefined) => {
      if (!f) return;
      if (!validate(f)) return;
      setPreview(f);
    },
    [validate],
  );

  const confirm = () => {
    if (preview) onUpload(preview);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      data-testid="upload-modal"
    >
      <div
        className="w-full max-w-[480px] rounded-[14px] border border-bordered bg-surface p-5"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Upload an image"
      >
        {!preview ? (
          <>
            <h2 className="mb-4 text-[20px] font-semibold tracking-[-0.02em]">
              Upload an image
            </h2>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pick(e.dataTransfer.files?.[0]);
              }}
              className={`flex h-[88px] w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed bg-transparent transition-colors ${
                dragging
                  ? 'border-accent bg-accent/10'
                  : 'border-bordered-strong hover:border-accent hover:bg-raised'
              }`}
              data-testid="dropzone"
            >
              <span className="text-[13px] font-medium text-primary">
                {dragging ? 'Drop to upload' : 'Drag & drop an image'}
              </span>
              <span className="text-[12px] text-muted">
                PNG, JPG, JPEG, WebP · up to {MAX_MB}MB
              </span>
            </button>
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                className="h-8 rounded-[10px] px-3 text-[13px] font-medium text-primary transition-colors hover:bg-raised"
                onClick={() => inputRef.current?.click()}
              >
                Browse files
              </button>
              <button
                type="button"
                className="h-8 rounded-[10px] px-3 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
                onClick={onClose}
              >
                Cancel
              </button>
            </div>
            {error && <p className="mt-3 text-[12px] text-danger">{error}</p>}
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              className="hidden"
              onChange={(e) => pick(e.target.files?.[0])}
            />
          </>
        ) : (
          <>
            <h2 className="mb-4 text-[20px] font-semibold tracking-[-0.02em]">
              Confirm upload
            </h2>
            <div className="flex items-center gap-3">
              <img
                src={URL.createObjectURL(preview)}
                alt="preview"
                className="h-24 w-[8.5rem] rounded-lg border border-bordered object-cover"
                data-testid="upload-preview"
              />
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-primary">
                  {preview.name}
                </p>
                <p className="text-[12px] text-muted">
                  {(preview.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="h-9 rounded-[10px] px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
                onClick={() => setPreview(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="h-9 rounded-[10px] bg-accent px-4 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
                onClick={confirm}
                data-testid="reconstruct-button"
              >
                Reconstruct →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}