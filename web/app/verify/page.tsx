'use client';
import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';

function VerifyContent() {
  const params = useSearchParams(); const token = params.get('token');
  const [message,setMessage] = useState('正在验证邮箱…');
  useEffect(()=>{ if(!token) { setMessage('验证链接缺少令牌'); return; } api(`/auth/verify?token=${encodeURIComponent(token)}`,{method:'POST'}).then(()=>setMessage('邮箱已验证，现在可以登录。')).catch(e=>setMessage((e as Error).message)); },[token]);
  return <main style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:20}}><div className="card card-pad" style={{maxWidth:430,width:'100%',textAlign:'center'}}><div className="brand-mark" style={{margin:'0 auto'}}>生</div><h1 style={{fontSize:28,marginTop:20}}>邮箱验证</h1><p className="subtle">{message}</p><Link className="button" href="/login">前往登录</Link></div></main>;
}

export default function VerifyPage() {
  return <Suspense fallback={<main className="workspace">正在验证邮箱…</main>}><VerifyContent/></Suspense>;
}
