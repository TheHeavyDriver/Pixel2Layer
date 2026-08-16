import { EditorScreen } from '@/components/editor/editor-screen';

export default async function EditorPage({
  searchParams,
}: {
  searchParams: Promise<{ job?: string }>;
}) {
  const { job } = await searchParams;
  return <EditorScreen jobId={job ?? null} />;
}