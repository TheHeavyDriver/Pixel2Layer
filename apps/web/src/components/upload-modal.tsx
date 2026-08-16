'use client';

import { useCallback, useRef, useState } from 'react';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  onUpload: (files: File[]) => void;
  multiple?: boolean;
}

const ACCEPTED = 'image/png,image/jpeg,image/webp';
const MAX_MB = 25;

export function UploadModal({ open, onClose, onUpload, multiple = false }: UploadModalProps) {
  const [previews, setPreviews] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = useCallback((files: FileList | File[]) => {
    const list = Array.from(files);
    for (const f of list) {
      if (!ACCEPTED.split(',').includes(f.type)) {
        setError('Unsupported file type. Please use PNG, JPG/JPEG, or WebP.');
        return false;
      }
      if (f.size > MAX_MB * 1024 * 1024) {
        setError(`File is over ${MAX_MB}MB. Please choose a smaller image.`);
        return false;
      }
    }
    setError(null);
    return true;
  }, []);

  const pick = useCallback(
    (files: FileList | File[]) => {
      const list = Array.from(files);
      if (list.length === 0) return;
      if (!validate(list)) return;
      setPreviews(multiple ? list : list.slice(0, 1));
    },
    [multiple, validate],
  );

  const confirm = () => {
    if (previews.length > 0) onUpload(previews);
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
        {previews.length === 0 ? (
          <>
            <h2 className="mb-4 text-[20px] font-semibold tracking-[-0.02em]">
              {multiple ? 'Upload images' : 'Upload an image'}
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
                pick(e.dataTransfer.files);
              }}
              className={`flex h-[88px] w-full flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed bg-transparent transition-colors ${
                dragging
                  ? 'border-accent bg-accent/10'
                  : 'border-bordered-strong hover:border-accent hover:bg-raised'
              }`}
              data-testid="dropzone"
            >
              <span className="text-[13px] font-medium text-primary">
                {dragging ? 'Drop to upload' : multiple ? 'Drag & drop images' : 'Drag & drop an image'}
              </span>
              <span className="text-[12px] text-muted">
                PNG, JPG, JPEG, WebP · up to {MAX_MB}MB {multiple ? 'each' : ''}
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
              multiple={multiple}
              className="hidden"
              onChange={(e) => {
                if (e.target.files) pick(e.target.files);
              }}
            />
          </>
        ) : (
          <>
            <h2 className="mb-4 text-[20px] font-semibold tracking-[-0.02em]">
              {multiple ? 'Confirm upload' : 'Confirm upload'}
            </h2>
            <ul className="flex flex-col gap-2">
              {previews.map((preview, i) => (
                <li key={`${preview.name}-${i}`} className="flex items-center gap-3">
                  <img
                    src={URL.createObjectURL(preview)}
                    alt="preview"
                    className="h-12 w-16 rounded-lg border border-bordered object-cover"
                    data-testid={i === 0 ? 'upload-preview' : undefined}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-primary">{preview.name}</p>
                    <p className="text-[12px] text-muted">
                      {(preview.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <button
                    type="button"
                    aria-label={`Remove ${preview.name}`}
                    onClick={() => setPreviews((prev) => prev.filter((_, j) => j !== i))}
                    className="h-7 rounded-[8px] px-2 text-[12px] font-medium text-danger transition-colors hover:bg-raised"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="h-9 rounded-[10px] px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
                onClick={() => setPreviews([])}
              >
                Cancel
              </button>
              <button
                type="button"
                className="h-9 rounded-[10px] bg-accent px-4 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
                onClick={confirm}
                data-testid="reconstruct-button"
              >
                Reconstruct {multiple && previews.length > 1 ? `(${previews.length})` : ''} →
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}