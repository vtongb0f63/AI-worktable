"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
const nav = [
  ["today", "今天", "◷"],
  ["schedule", "周日程", "▦"],
  ["news", "每日新闻", "▤"],
  ["words", "词汇学习", "Aa"],
  ["running", "跑步", "↗"],
  ["journal", "日志", "≡"],
];
export default function Shell({
  children,
  username,
}: {
  children: React.ReactNode;
  username: string;
}) {
  const pathname = usePathname(),
    router = useRouter();
  return (
    <div className="desk-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside className="sidebar">
        <Link href="/today" className="brand">
          <span className="brand-symbol" aria-hidden="true">
            日
          </span>
          <span>
            日课<small>学习 · 生活 · 跑步</small>
          </span>
        </Link>
        <div className="notebook-rule" />
        <p className="nav-caption">我的日常</p>
        <nav aria-label="主导航">
          {nav.map(([path, label, icon]) => (
            <Link
              key={path}
              href={`/${path}`}
              className={
                pathname === `/${path}` ? "nav-link active" : "nav-link"
              }
              aria-current={pathname === `/${path}` ? "page" : undefined}
            >
              <span aria-hidden="true" className="nav-icon">
                {icon}
              </span>
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Link className="nav-link" href="/settings">
            ⚙ <span>偏好与目标</span>
          </Link>
          <Link className="subtle-link" href="/history">
            历史目标
          </Link>
          <div className="profile">
            <span className="avatar">{username.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{username}</strong>
              <small>私人工作台</small>
            </div>
            <button
              className="icon-button"
              title="退出登录"
              aria-label="退出登录"
              onClick={async () => {
                await api("/auth/logout", { method: "POST" });
                router.replace("/login");
                router.refresh();
              }}
            >
              ↪
            </button>
          </div>
        </div>
      </aside>
      <main id="main-content" className="main-content">
        {children}
        <footer className="page-footer">
          <span>一步一步，把日子过成想要的样子。</span>
          <span>北京时间 · 仅自己可见</span>
        </footer>
      </main>
    </div>
  );
}
