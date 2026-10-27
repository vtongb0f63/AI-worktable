"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
export default function LoginPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-symbol">日</span>日课
        </div>
        <div>
          <p className="eyebrow">A LITTLE PROGRESS, EVERY DAY</p>
          <h1>
            今天的事，
            <br />
            一页一页地完成。
          </h1>
          <p>
            为学习留出时间，为跑步留出空间。
            <br />
            把想做的事，慢慢变成做过的事。
          </p>
          <div className="paper-illustration" aria-hidden="true">
            <span>我的一天</span>
            <i />
            <i />
            <i />
            <b>✓</b>
          </div>
        </div>
        <p className="muted">学习 · 阅读 · 词汇 · 跑步</p>
      </section>
      <section className="login-form">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            setBusy(true);
            setError("");
            try {
              await api("/auth/login", {
                method: "POST",
                body: JSON.stringify({
                  email: data.get("email"),
                  password: data.get("password"),
                }),
              });
              router.replace("/today");
              router.refresh();
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <p className="eyebrow">欢迎回来</p>
          <h2>翻开你的手帐</h2>
          <p className="muted">登录后，查看今天的安排与记录。</p>
          <label>
            邮箱
            <input
              name="email"
              type="email"
              autoComplete="email"
              spellCheck={false}
              required
              placeholder="name@example.com…"
            />
          </label>
          <label>
            密码
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {error ? (
            <p className="notice error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="button" disabled={busy}>
            {busy ? "正在登录…" : "进入我的工作台 →"}
          </button>
          <p className="private-note">仅供本人使用 · 所有记录私密保存</p>
        </form>
      </section>
    </main>
  );
}
