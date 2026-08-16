import { EditorScreen } from '@/components/editor/editor-screen';

export default async function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <EditorScreen jobId={null} projectId={null} shareToken={token} />;
}

export async function generateMetadata({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return { title: `Shared design — Pixel2Layer`, robots: { index: false, follow: false } };
}