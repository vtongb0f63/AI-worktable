'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
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
    try { await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }); router.push('/'); router.refresh(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <main className="auth-page"><section className="auth-art"><div className="brand"><span className="brand-mark">生</span>生长</div><div><div className="eyebrow" style={{color:'#b6d9d7'}}>YOUR FOUR YEAR JOURNEY</div><h1>把远方，<br/>落在今天。</h1><p style={{color:'#c5d5e5',maxWidth:420,lineHeight:1.8}}>一棵由行动长成的树。写下愿景，选好本周重点，做好今天的三件事。</p></div><div className="footer-note">每一步都算数。</div></section><section className="auth-form-wrap"><form className="auth-form" onSubmit={submit}><div className="eyebrow">WELCOME BACK</div><h2>继续生长</h2><p className="subtle">登录后查看你的目标与今日计划。</p>{error && <div className="error">{error}</div>}{notice && <div className="notice">{notice}</div>}<label className="field-label" htmlFor="login-email">邮箱</label><input id="login-email" className="field" type="email" required value={email} onChange={e=>setEmail(e.target.value)}/><label className="field-label" htmlFor="login-password">密码</label><input id="login-password" className="field" type="password" required value={password} onChange={e=>setPassword(e.target.value)}/><button className="button" style={{width:'100%',marginTop:24}} disabled={busy}>{busy?'正在登录…':'登录'}</button><button type="button" className="button quiet" style={{width:'100%',marginTop:10}} disabled={!email||busy} onClick={async()=>{setError('');try{const data=await api<{message:string;dev_verification_url?:string}>('/auth/resend-verification',{method:'POST',body:JSON.stringify({email})});setNotice(data.dev_verification_url||data.message);}catch(e){setError((e as Error).message);}}}>重发验证邮件</button><p className="subtle" style={{marginTop:20}}>还没有账号？ <Link href="/register" style={{color:'#355b95',fontWeight:700}}>用邀请码注册</Link></p></form></section></main>;
}
