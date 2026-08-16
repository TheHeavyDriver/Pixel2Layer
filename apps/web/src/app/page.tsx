'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { BatchProgressScreen } from '@/components/batch-progress-screen';
import { ProgressScreen } from '@/components/progress-screen';
import { UploadModal } from '@/components/upload-modal';
import {
  createBatch,
  createJob,
  getCurrentUser,
  logout,
  uploadImage,
  type AuthUser,
  type Batch,
  type JobResponse,
} from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadMultiple, setUploadMultiple] = useState(false);
  const [activeJob, setActiveJob] = useState<string | null>(null);
  const [activeBatch, setActiveBatch] = useState<Batch | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getCurrentUser().then((me) => {
      if (!cancelled) setUser(me);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleUpload(files: File[]) {
    setUploadOpen(false);
    setError(null);
    try {
      if (files.length === 1) {
        const upload = await uploadImage(files[0]);
        const job = await createJob(upload.uploadId);
        setActiveJob(job.id);
      } else {
        setBatchBusy(true);
        const uploads = [];
        for (const file of files) {
          uploads.push(await uploadImage(file));
        }
        const batch = await createBatch(uploads.map((u) => u.uploadId));
        setActiveBatch(batch);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setBatchBusy(false);
    }
  }

  function handleDone(job: JobResponse | undefined) {
    router.push(`/editor?job=${job?.id ?? ''}`);
  }

  if (activeBatch) {
    return (
      <BatchProgressScreen
        batchId={activeBatch.id}
        initialJobs={activeBatch.jobs}
        onCancel={() => setActiveBatch(null)}
      />
    );
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
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <button
                type="button"
                onClick={() => router.push('/dashboard')}
                className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
              >
                My projects
              </button>
              <button
                type="button"
                onClick={() => {
                  logout();
                  setUser(null);
                }}
                className="h-9 rounded-[10px] px-3 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
              >
                Log out
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => router.push('/login')}
              className="h-9 rounded-[10px] border border-bordered px-4 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
            >
              Sign in
            </button>
          )}
        </div>
      </nav>

      <div className="pt-16">
        <h1 className="max-w-2xl text-center text-[40px] font-semibold leading-tight tracking-[-0.02em]">
          Recover the design behind the image
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-center text-[16px] text-secondary">
          Drop a flat poster and get back text, shapes, vectors, and layers — fully editable.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => {
              setUploadMultiple(false);
              setUploadOpen(true);
            }}
            disabled={batchBusy}
            className="h-[40px] rounded-[10px] bg-accent px-6 text-[13px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {batchBusy ? 'Uploading…' : 'Upload an image'}
          </button>
          <button
            type="button"
            onClick={() => {
              setUploadMultiple(true);
              setUploadOpen(true);
            }}
            disabled={batchBusy}
            className="h-[40px] rounded-[10px] border border-bordered px-6 text-[13px] font-medium text-secondary transition-colors hover:bg-raised disabled:opacity-50"
          >
            Upload multiple
          </button>
          <button
            type="button"
            onClick={() => router.push('/templates')}
            className="h-[40px] rounded-[10px] border border-bordered px-6 text-[13px] font-medium text-secondary transition-colors hover:bg-raised"
          >
            Template gallery
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
        onUpload={(files) => void handleUpload(files)}
        multiple={uploadMultiple}
      />
    </main>
  );
}