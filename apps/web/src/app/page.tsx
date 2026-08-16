'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { ProgressScreen } from '@/components/progress-screen';
import { UploadModal } from '@/components/upload-modal';
import { createJob, uploadImage, type JobResponse } from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [activeJob, setActiveJob] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setUploadOpen(false);
    setError(null);
    try {
      const upload = await uploadImage(file);
      const job = await createJob(upload.uploadId);
      setActiveJob(job.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
    }
  }

  function handleDone(job: JobResponse | undefined) {
    // v0.1: no editor yet — surface the completed job id; editor lands in v0.2.
    router.push(`/editor?job=${job?.id ?? ''}`);
  }

  if (activeJob) {
    return <ProgressScreen jobId={activeJob} onDone={handleDone} onCancel={() => setActiveJob(null)} />;
  }
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-base px-4">
      <nav className="fixed top-0 flex w-full max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2">
          <span className="h-5 w-5 rounded-[4px] bg-accent" aria-hidden />
          <span className="text-[15px] font-semibold tracking-[-0.02em]">Pixel2Layer</span>
        </div>
        <button
          type="button"
          className="h-10 rounded-[10px] bg-accent px-5 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
          onClick={() => setUploadOpen(true)}
        >
          Get started →
        </button>
      </nav>

      <div className="pt-16">
        <h1 className="max-w-2xl text-center text-[40px] font-semibold leading-tight tracking-[-0.02em]">
          Recover the design behind the image
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-center text-[16px] text-secondary">
          Drop a flat poster and get back text, shapes, vectors, and layers — fully editable.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            className="h-[40px] rounded-[10px] bg-accent px-6 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover"
          >
            Upload an image
          </button>
          <button
            type="button"
            className="h-[40px] rounded-[10px] border border-bordered px-6 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
          >
            Try a sample
          </button>
        </div>

        {error && (
          <p className="mt-6 text-center text-[13px] text-danger" data-testid="upload-error">
            {error}
          </p>
        )}
      </div>

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUpload={handleUpload}
      />
    </main>
  );
}