'use client';
import { useState } from 'react';
import { api, ApiError } from '@/lib/api';

export default function ReportButton({nodeId}:{nodeId:string}) {
  const [open,setOpen]=useState(false);const [reason,setReason]=useState('');const [message,setMessage]=useState('');
  async function submit() { try { await api('/reports',{method:'POST',body:JSON.stringify({node_id:nodeId,reason})});setMessage('举报已提交');setOpen(false); } catch(e) { setMessage(e instanceof ApiError && e.status===401?'请先登录后提交举报。':(e as Error).message); } }
  return <span style={{display:'inline-flex',alignItems:'center',gap:7}}><button className="button quiet small" onClick={()=>setOpen(!open)}>举报</button>{open&&<><input className="field" style={{width:180}} value={reason} minLength={5} maxLength={1000} onChange={e=>setReason(e.target.value)} placeholder="说明原因（至少 5 字）"/><button className="button small" disabled={reason.length<5} onClick={submit}>提交</button></>}{message&&<span className="subtle">{message}</span>}</span>;
}
