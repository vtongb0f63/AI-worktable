'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function ShareProfile({ username }: { username: string }) {
  const path = `/u/${encodeURIComponent(username)}`;
  const [url, setUrl] = useState(path);
  const [message, setMessage] = useState('');

  useEffect(() => setUrl(`${window.location.origin}${path}`), [path]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${path}`);
      setMessage('链接已复制，可以直接发给老师。');
    } catch {
      setMessage('无法自动复制，请选中上方链接后手动复制。');
    }
  }

  return <div className="share-profile">
    <label className="field-label" htmlFor="public-profile-url">公开主页链接</label>
    <input id="public-profile-url" className="field" readOnly value={url} onFocus={event=>event.currentTarget.select()}/>
    <div className="share-actions">
      <button className="button" type="button" onClick={copyLink}>复制链接</button>
      <Link className="button secondary" href={path} target="_blank">预览公开主页 ↗</Link>
    </div>
    {message && <p className="field-help" role="status">{message}</p>}
  </div>;
}
