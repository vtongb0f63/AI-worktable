import TreeGraphic from '@/components/TreeGraphic';
import ReportButton from '@/components/ReportButton';
import { kindLabel, type Node } from '@/lib/api';

export const dynamic = 'force-dynamic';

export default async function PublicPage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = await params;
  const base = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
  const response = await fetch(`${base}/api/public/${encodeURIComponent(username)}`, { cache: 'no-store' });
  if (!response.ok) return <main className="workspace"><h1 className="page-title">这个公开主页不存在</h1><a className="button" href="/">返回首页</a></main>;
  const data: {username:string;nodes:Node[]} = await response.json();
  const roots = data.nodes.filter(x=>x.kind==='vision');
  return <main className="workspace" style={{maxWidth:1040}}><header className="topline"><a href="/" className="brand" style={{color:'#42583a',padding:0}}><span className="brand-mark">生</span>生长</a><a className="button secondary" href="/login">登录</a></header><div className="eyebrow">PUBLIC GROWTH PAGE</div><h1 className="page-title">{data.username} 的成长树</h1><p className="subtle">这里仅展示主人主动公开的目标和任务。公开进度只由公开内容计算。</p><section className="card card-pad" style={{marginTop:25}}><TreeGraphic nodes={data.nodes}/></section><div className="section-head"><h2>公开目标</h2></div><section className="card">{data.nodes.length ? data.nodes.map(node=><div className="node-row" key={node.id}><div className="node-content"><div className="node-title">{node.title}</div><div className="node-meta">{kindLabel[node.kind]} {node.due_on || node.starts_on || ''}</div></div><div style={{fontFamily:'Georgia,serif',color:'#657e45'}}>{node.progress}%</div><ReportButton nodeId={node.id}/></div>) : <div className="card-pad subtle">还没有公开内容。</div>}</section><p className="footer-note">发现不合适的公开内容，可在对应目标旁提交举报。</p>{roots.length>0 && <p className="footer-note">四年愿景进度：{roots[0].progress}%</p>}</main>;
}
