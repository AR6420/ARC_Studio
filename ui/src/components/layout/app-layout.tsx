/**
 * Main application layout shell.
 *
 * Two-column layout: fixed narrow sidebar on the left, main area on the
 * right with a thin header and scrollable content. Max-width is 1240px
 * so the content stays legible on wide monitors without feeling lost.
 */

import { Outlet } from 'react-router-dom';
import { Sidebar } from '@/components/layout/sidebar';
import { Header } from '@/components/layout/header';

interface AppLayoutProps {
  title?: string;
}

export function AppLayout({ title }: AppLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header title={title} />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1240px] px-8 py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
