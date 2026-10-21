"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  News as NewsItem,
  Page,
  useData,
  todayLocal,
  categoryName,
  post,
  Word,
} from "@/lib/planner";
import {
  PageHeading,
  Notice,
  Empty,
  Loading,
  AIButton,
  JobPanel,
  RecordForm,
  Pagination,
} from "./Shared";
export function NewsCard({
  item,
  onChanged,
  onWord,
}: {
  item: NewsItem;
  onChanged: () => void;
  onWord: (context: string) => void;
}) {
  const [english, setEnglish] = useState(true),
    [error, setError] = useState("");
  return (
    <article className="news-card">
      <div className="news-meta">
        <span className={`category ${item.category}`}>
          {categoryName[item.category]}
        </span>
        <span>{item.source}</span>
        <time dateTime={item.published_at}>
          {new Intl.DateTimeFormat("zh-CN", {
            timeZone: "Asia/Shanghai",
            month: "numeric",
            day: "numeric",
          }).format(new Date(item.published_at))}
        </time>
      </div>
      <h2>{item.title}</h2>
      {item.summary_zh ? (
        <p className="news-summary">{item.summary_zh}</p>
      ) : (
        <p className="muted">摘要等待生成，可先阅读原始来源。</p>
      )}
      {item.summary_en ? (
        <>
          <button
            className="english-toggle"
            onClick={() => setEnglish(!english)}
            aria-expanded={english}
          >
            English summary <span>{english ? "−" : "＋"}</span>
          </button>
          {english ? (
            <blockquote lang="en">{item.summary_en}</blockquote>
          ) : null}
        </>
      ) : null}
      <div className="news-actions">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="text-link"
        >
          阅读来源 ↗
        </a>
        <button
          className="button small quiet"
          onClick={() => onWord(item.summary_en)}
        >
          ＋ 加入生词
        </button>
        <button
          className="button small quiet"
          aria-pressed={item.bookmarked}
          onClick={async () => {
            try {
              await post(`/news/${item.id}/bookmark`, {});
              onChanged();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          {item.bookmarked ? "★ 已收藏" : "☆ 收藏"}
        </button>
      </div>
      <Notice text={error} error />
    </article>
  );
}
export default function News() {
  const params = useSearchParams(),
    router = useRouter();
  const day = params.get("day") || todayLocal(),
    category = params.get("category") || "";
  const [jobRevision, setJobRevision] = useState(0),
    [offset, setOffset] = useState(0),
    [word, setWord] = useState<{ term: string; example: string; source: string } | null>(null),
    [notice, setNotice] = useState("");
  const { data, error, loading, reload } = useData<
    Page<NewsItem> & {
      editions: { date: string; errors: string[]; status: string }[];
    }
  >(
    `/news?day=${day}&limit=50&offset=${offset}${category ? `&category=${category}` : ""}`,
  );
  function filter(d: string, c: string) {
    setOffset(0);
    router.replace(`/news?day=${d}${c ? `&category=${c}` : ""}`);
  }
  return (
    <>
      <PageHeading
        eyebrow="A WINDOW TO THE WORLD"
        title="每日一读。"
        description="把重要的消息读清楚，也把英语读进日常。"
      >
        <label className="date-control">
          <span className="sr-only">日报日期</span>
          <input
            type="date"
            name="news_date"
            value={day}
            onChange={(e) => e.target.value && filter(e.target.value, category)}
          />
        </label>
        <AIButton
          kind="news"
          label="✦ 整理今天的日报"
          onQueued={() => setJobRevision((v) => v + 1)}
        />
      </PageHeading>
      <nav className="filter-tabs" aria-label="新闻分类">
        {[
          ["", "全部"],
          ["domestic", "国内"],
          ["international", "国际"],
          ["ai", "AI 模型"],
          ["running", "中长跑"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={category === value ? "active" : ""}
            aria-pressed={category === value}
            onClick={() => filter(day, value)}
          >
            {label}
          </button>
        ))}
      </nav>
      <Notice text={error} error />
      <Notice text={notice} />
      {data?.editions.find((e) => e.date === day)?.errors.length ? (
        <Notice
          text={data.editions.find((e) => e.date === day)!.errors.join("；")}
        />
      ) : null}
      {loading && !data ? <Loading /> : null}
      {data?.items.length ? (
        <div className="news-grid">
          {data.items.map((item) => (
            <NewsCard
              key={item.id}
              item={item}
              onChanged={reload}
              onWord={(example) =>
                setWord({
                  term:
                    window.getSelection()?.toString().trim().slice(0, 100) ||
                    "",
                  example,
                  source: item.url,
                })
              }
            />
          ))}
        </div>
      ) : !loading ? (
        <Empty title="这一期还没有新闻">
          每天 7
          点自动整理；你也可以点击上方按钮生成今天的日报。只收录有来源的消息。
        </Empty>
      ) : null}
      <Pagination
        offset={offset}
        total={data?.total || 0}
        onChange={setOffset}
      />
      <JobPanel refreshKey={jobRevision} onFinished={reload} />
      {word ? (
        <RecordForm
          title="把生词记下来"
          initial={word}
          fields={[
            { name: "term", label: "单词或短语", required: true },
            { name: "meaning", label: "中文释义（可稍后补全）" },
            { name: "example", label: "原文语境", type: "textarea" },
            { name: "tags", label: "标签", placeholder: "例如：新闻、AI…" },
          ]}
          onClose={() => setWord(null)}
          onSave={async (value) => {
            await post<Word>("/records/words", {
              ...value,
              source: word.source,
            });
            setNotice("已加入个人词汇表");
          }}
        />
      ) : null}
    </>
  );
}
