'use client';
export default function ErrorPage({reset}:{reset:()=>void}){return <section className="empty"><h1>这一页暂时没能打开</h1><p>请检查网络连接，再试一次。</p><button className="button" onClick={reset}>重新加载</button></section>;}
