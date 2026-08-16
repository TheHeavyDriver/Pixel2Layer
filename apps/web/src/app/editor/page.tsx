import { EditorScreen } from '@/components/editor/editor-screen';

export default async function EditorPage({
  searchParams,
}: {
  searchParams: Promise<{ job?: string; project?: string }>;
}) {
  const { job, project } = await searchParams;
  return <EditorScreen jobId={job ?? null} projectId={project ?? null} />;
}