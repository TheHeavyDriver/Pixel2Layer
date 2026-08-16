import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Pixel2Layer — Recover the design behind the image',
  description:
    'Upload a flattened poster and get back text, shapes, vectors, and layers — fully editable.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}