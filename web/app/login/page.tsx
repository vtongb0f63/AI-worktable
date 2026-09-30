'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import SproutAnimation from '@/components/SproutAnimation';
import { api } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      router.push('/'); router.refresh();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <main className="auth-page">
    <section className="auth-art">
      <div className="brand"><span className="brand-mark">生</span>生长</div>
      <SproutAnimation/>
      <div className="auth-story">
        <div className="eyebrow">THE GARDEN / 你的成长花园</div>
        <h1>回来看看，<br/>今天长出了什么。</h1>
        <p>把四年的远方种在这里，每一天都照顾它一点。</p>
      </div>
      <div className="footer-note">一粒种子，也有自己的节奏。</div>
    </section>
    <section className="auth-form-wrap">
      <form className="auth-form" onSubmit={submit}>
        <div className="eyebrow">WELCOME BACK</div>
        <h2>继续生长</h2>
        <p className="subtle">登录后查看你的目标与今日计划。</p>
        {error && <div className="error" role="alert">{error}</div>}
        {notice && <div className="notice" role="status">{notice}</div>}
        <label className="field-label" htmlFor="login-email">邮箱</label>
        <input id="login-email" className="field" type="email" autoComplete="email" required
          value={email} onChange={e=>setEmail(e.target.value)}/>
        <label className="field-label" htmlFor="login-password">密码</label>
        <input id="login-password" className="field" type="password" autoComplete="current-password" required
          value={password} onChange={e=>setPassword(e.target.value)}/>
        <button className="button auth-submit" disabled={busy}>{busy?'正在登录…':'登录'}</button>
        <button type="button" className="button quiet auth-resend" disabled={!email||busy} onClick={async()=>{
          setError('');
          try {
            const data = await api<{message:string;dev_verification_url?:string}>('/auth/resend-verification',{method:'POST',body:JSON.stringify({email})});
            setNotice(data.dev_verification_url||data.message);
          } catch(e) { setError((e as Error).message); }
        }}>重发验证邮件</button>
        <p className="subtle auth-switch">还没有账号？ <Link href="/register" className="auth-link">用邀请码注册</Link></p>
      </form>
    </section>
  </main>;
}
