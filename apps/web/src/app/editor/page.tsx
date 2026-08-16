import { EditorScreen } from '@/components/editor/editor-screen';

export default async function EditorPage({
  searchParams,
}: {
  searchParams: Promise<{ job?: string; project?: string; share?: string; template?: string }>;
}) {
  const { job, project, share, template } = await searchParams;
  return <EditorScreen jobId={job ?? null} projectId={project ?? null} shareToken={share ?? null} templateId={template ?? null} />;
}