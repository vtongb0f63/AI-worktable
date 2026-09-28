import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '生长 · 把远方落在今天',
  description: '从四年愿景到今天的三件事，记录每一步生长。',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
