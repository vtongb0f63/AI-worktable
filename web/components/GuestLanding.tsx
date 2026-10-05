'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import SproutAnimation from './SproutAnimation';

export default function GuestLanding() {
  const router = useRouter();
  const [username, setUsername] = useState('');

  function openProfile(event: React.FormEvent) {
    event.preventDefault();
    router.push(`/u/${encodeURIComponent(username.trim().toLowerCase())}`);
  }

  return <main className="guest-page">
    <header className="guest-header">
      <Link href="/" className="brand"><span className="brand-mark">生</span>生长</Link>
      <div className="guest-header-actions"><Link className="button quiet" href="/login">登录</Link><Link className="button" href="/register">注册</Link></div>
    </header>
    <div className="guest-layout">
      <section className="guest-story">
        <div className="eyebrow">GROWTH GARDEN / 公开成长花园</div>
        <h1>看看一棵树，<br/>是怎样慢慢长大的。</h1>
        <p>作者可以选择公开自己的目标、进度和成长树。作为访客，你无需注册就能查看他们分享的主页。</p>
        <SproutAnimation/>
      </section>
      <section className="card guest-lookup" aria-labelledby="guest-lookup-title">
        <div className="eyebrow">VISIT A GARDEN</div>
        <h2 id="guest-lookup-title">查看公开档案</h2>
        <p className="subtle">请输入对方分享的用户名，或直接打开对方发给你的专属链接。</p>
        <form onSubmit={openProfile}>
          <label className="field-label" htmlFor="guest-username">用户名</label>
          <input id="guest-username" className="field" required minLength={3} maxLength={24}
            pattern="[a-zA-Z0-9_]+" autoComplete="off" placeholder="例如：garden_friend"
            value={username} onChange={event=>setUsername(event.target.value)}/>
          <button className="button auth-submit">打开公开主页 →</button>
        </form>
        <p className="field-help">公开主页地址格式：本站域名/u/用户名。只有作者主动公开的内容可见。</p>
      </section>
    </div>
  </main>;
}
