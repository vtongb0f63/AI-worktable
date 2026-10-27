import { notFound } from 'next/navigation';
import { Suspense } from 'react';
import Today from '@/components/planner/Today';
import Schedule from '@/components/planner/Schedule';
import News from '@/components/planner/News';
import Words from '@/components/planner/Words';
import Running from '@/components/planner/Running';
import Journal from '@/components/planner/Journal';
import Settings from '@/components/planner/Settings';
import History from '@/components/planner/History';
const pages:Record<string,React.ComponentType>={today:Today,schedule:Schedule,news:News,words:Words,running:Running,journal:Journal,settings:Settings,history:History};
export default async function Page({params}:{params:Promise<{section:string}>}){const {section}=await params;const Component=pages[section];if(!Component)notFound();return <Suspense fallback={<p role="status">正在加载…</p>}><Component/></Suspense>;}
