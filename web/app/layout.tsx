import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '日课 · 私人学习手帐',
  description: '安排学习、积累词汇、记录跑步，把每一天落在纸上。',
  robots: {index:false,follow:false},
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN" data-scroll-behavior="smooth"><body>{children}</body></html>;
}
