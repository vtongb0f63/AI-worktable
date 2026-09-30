'use client';
import { useState } from 'react';
import Link from 'next/link';
import SproutAnimation from '@/components/SproutAnimation';
import { api } from '@/lib/api';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [invite, setInvite] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const data = await api<{message:string;dev_verification_url?:string}>('/auth/register', {
        method:'POST', body:JSON.stringify({email,username,password,invite_code:invite}),
      });
      setMessage(data.dev_verification_url ? `开发环境验证链接：${data.dev_verification_url}` : data.message);
    } catch(e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <main className="auth-page">
    <section className="auth-art">
      <div className="brand"><span className="brand-mark">生</span>生长</div>
      <SproutAnimation/>
      <div className="auth-story">
        <div className="eyebrow">A NEW SEED / 新的开始</div>
        <h1>四年很长，<br/>先种下一粒种子。</h1>
        <p>给目标一个方向，也给每天留一个能够完成的小步骤。</p>
      </div>
      <div className="footer-note">邀请制开放中 · 从这里开始生长</div>
    </section>
    <section className="auth-form-wrap">
      <form className="auth-form" onSubmit={submit}>
        <div className="eyebrow">JOIN THE GARDEN</div>
        <h2>创建账号</h2>
        <p className="subtle">注册后，我们会给你的邮箱发送验证链接。</p>
        {error && <div className="error" role="alert">{error}</div>}
        {message && <div className="notice" role="status" style={{wordBreak:'break-all'}}>{message}</div>}
        <label className="field-label" htmlFor="register-email">邮箱</label>
        <input id="register-email" className="field" type="email" autoComplete="email" required
          value={email} onChange={e=>setEmail(e.target.value)}/>
        <label className="field-label" htmlFor="register-username">用户名（公开主页地址）</label>
        <input id="register-username" className="field" minLength={3} maxLength={24} pattern="[a-zA-Z0-9_]+"
          autoComplete="username" required value={username} onChange={e=>setUsername(e.target.value)}/>
        <p className="field-help">3–24 位英文字母、数字或下划线。</p>
        <label className="field-label" htmlFor="register-password">密码（至少 12 位）</label>
        <input id="register-password" className="field" type="password" minLength={12}
          autoComplete="new-password" required value={password} onChange={e=>setPassword(e.target.value)}/>
        <label className="field-label" htmlFor="register-invite">邀请码</label>
        <input id="register-invite" className="field" required value={invite} onChange={e=>setInvite(e.target.value)}/>
        <button className="button auth-submit" disabled={busy}>{busy?'正在创建…':'创建账号'}</button>
        <p className="subtle auth-switch">已有账号？ <Link href="/login" className="auth-link">去登录</Link></p>
      </form>
    </section>
  </main>;
}
