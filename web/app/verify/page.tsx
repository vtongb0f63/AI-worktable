'use client';
import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';

function VerifyContent() {
  const [message,setMessage] = useState('正在验证邮箱…');
  useEffect(()=>{
    const url = new URL(window.location.href);
    const fragmentParams = new URLSearchParams(url.hash.slice(1));
    // Accept links sent by the previous release while new emails use fragments.
    const token = fragmentParams.get('token') || url.searchParams.get('token');
    if(!token) { setMessage('验证链接缺少令牌'); return; }
    window.history.replaceState(null, '', url.pathname);
    api('/auth/verify',{method:'POST',body:JSON.stringify({token})})
      .then(()=>setMessage('邮箱已验证，现在可以登录。'))
      .catch(e=>setMessage((e as Error).message));
  },[]);
  return <main style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:20}}><div className="card card-pad" style={{maxWidth:430,width:'100%',textAlign:'center'}}><div className="brand-mark" style={{margin:'0 auto'}}>生</div><h1 style={{fontSize:28,marginTop:20}}>邮箱验证</h1><p className="subtle">{message}</p><Link className="button" href="/login">前往登录</Link></div></main>;
}

export default function VerifyPage() {
  return <Suspense fallback={<main className="workspace">正在验证邮箱…</main>}><VerifyContent/></Suspense>;
}
