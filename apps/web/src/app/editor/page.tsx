export default async function EditorPage({
  searchParams,
}: {
  searchParams: Promise<{ job?: string }>;
}) {
  const { job } = await searchParams;
  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas-drop">
      <div className="rounded-lg border border-bordered bg-surface p-8 text-center">
        <h1 className="text-[20px] font-semibold tracking-[-0.02em]">Editor</h1>
        <p className="mt-2 text-[13px] text-secondary">
          Reconstruction complete {job ? `(job ${job})` : ''}. The Fabric.js editor ships in
          v0.2.
        </p>
      </div>
    </main>
  );
}