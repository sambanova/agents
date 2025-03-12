import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Agent Crew',
  description: 'Financial analysis and research tool',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}