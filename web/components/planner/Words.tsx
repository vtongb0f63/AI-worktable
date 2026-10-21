"use client";
import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Word,
  Entity,
  Job,
  Page,
  useData,
  todayLocal,
  put,
  post,
  clean,
  wordKeys,
  request,
} from "@/lib/planner";
import {
  PageHeading,
  RecordForm,
  Field,
  Notice,
  Empty,
  Loading,
  Pagination,
  JobPanel,
} from "./Shared";
export const wordFields: Field[] = [
  { name: "term", label: "单词或短语", required: true },
  { name: "part_of_speech", label: "词性" },
  { name: "meaning", label: "中文释义", type: "textarea" },
  { name: "example", label: "英文例句 / 语境", type: "textarea" },
  { name: "tags", label: "标签", placeholder: "新闻、数学、日常…" },
  { name: "source", label: "来源（可选）" },
];
type Question = Entity & {
  word_id: string;
  mode: string;
  prompt: string;
  options: string[];
  attempt?: string;
};
type Attempt = Entity & {
  question_id: string;
  answer: string;
  correct: boolean | null;
  feedback: string;
  expected?: string;
  status: string;
};
function Quiz({ id, onChanged }: { id: string; onChanged: () => void }) {
  const questions = useData<Question[]>(`/questions?job_id=${id}`),
    attempts = useData<Attempt[]>(`/attempts?job_id=${id}`);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState("");
  useEffect(() => {
    if (questions.data?.length) return;
    const timer = setInterval(questions.reload, 4000);
    return () => clearInterval(timer);
  }, [questions.data, questions.reload]);
  useEffect(() => {
    if (!attempts.data?.some((a) => a.status === "pending")) return;
    const timer = setInterval(() => {
      attempts.reload();
      onChanged();
    }, 4000);
    return () => clearInterval(timer);
  }, [attempts.data, attempts.reload, onChanged]);
  return (
    <section className="paper-panel quiz-panel">
      <div className="section-heading">
        <h2>这一组，认真练习</h2>
        <span className="tag">{questions.data?.length || 0} 题</span>
      </div>
      <Notice text={error || questions.error} error />
      {!questions.data?.length ? (
        <p className="muted">题目正在整理，完成后请点击“刷新题目”。</p>
      ) : null}
      <button
        className="button small secondary"
        onClick={() => {
          questions.reload();
          attempts.reload();
        }}
      >
        刷新题目
      </button>
      {questions.data?.map((q, index) => {
        const attempt = attempts.data?.find((a) => a.question_id === q.id);
        return (
          <form
            className="question"
            key={q.id}
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(q.id);
              try {
                const answer = new FormData(e.currentTarget).get("answer");
                await post(`/questions/${q.id}/answers`, { answer });
                questions.reload();
                attempts.reload();
                onChanged();
              } catch (err) {
                setError((err as Error).message);
              } finally {
                setBusy("");
              }
            }}
          >
            <p className="eyebrow">
              练习 {index + 1} ·{" "}
              {q.mode === "dictation"
                ? "默写"
                : q.mode === "choice"
                  ? "词义辨析"
                  : "句子翻译"}
            </p>
            <h3>{q.prompt}</h3>
            {attempt ? (
              <div
                className={`answer-result ${attempt.correct === false ? "incorrect" : ""}`}
              >
                <p>
                  <strong>
                    {attempt.status === "pending"
                      ? "等待 AI 批改"
                      : attempt.correct
                        ? "回答正确"
                        : "再巩固一下"}
                  </strong>{" "}
                  · 你的答案：{attempt.answer}
                </p>
                <p>参考答案：{attempt.expected}</p>
                <p>{attempt.feedback}</p>
                {attempt.status === "graded" ? (
                  <button
                    type="button"
                    className="button small quiet"
                    onClick={async () => {
                      try {
                        await post(`/attempts/${attempt.id}/correction`, {
                          correct: !attempt.correct,
                        });
                        attempts.reload();
                        onChanged();
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    更正为{attempt.correct ? "答错" : "答对"}
                  </button>
                ) : null}
              </div>
            ) : (
              <>
                <fieldset>
                  <legend className="sr-only">第 {index + 1} 题答案</legend>
                  {q.mode === "choice" ? (
                    q.options.map((option) => (
                      <label className="choice" key={option}>
                        <input
                          type="radio"
                          name="answer"
                          value={option}
                          required
                        />
                        {option}
                      </label>
                    ))
                  ) : q.mode === "translation" ? (
                    <label>
                      你的翻译
                      <textarea
                        name="answer"
                        rows={3}
                        required
                        autoComplete="off"
                      />
                    </label>
                  ) : (
                    <label>
                      填写单词
                      <input
                        name="answer"
                        required
                        autoComplete="off"
                        spellCheck={false}
                      />
                    </label>
                  )}
                </fieldset>
                <button className="button small" disabled={busy === q.id}>
                  {busy === q.id ? "正在提交…" : "提交答案"}
                </button>
              </>
            )}
          </form>
        );
      })}
    </section>
  );
}
export default function Words() {
  const router = useRouter(),
    params = useSearchParams(),
    quiz = params.get("quiz");
  const [offset, setOffset] = useState(0),
    [search, setSearch] = useState(params.get("q") || ""),
    [filter, setFilter] = useState("all"),
    [selected, setSelected] = useState<string[]>([]),
    [editing, setEditing] = useState<Word | "new" | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [jobRevision, setJobRevision] = useState(0),
    [mode, setMode] = useState("dictation"),
    [direction, setDirection] = useState("zh-en"),
    [busy, setBusy] = useState(false);
  const words = useData<Page<Word>>(
    `/records/words?offset=${offset}&limit=50&q=${encodeURIComponent(params.get("q") || "")}&filter=${filter}`,
  );
  const suggestions =
    useData<
      {
        id: string;
        version: number;
        words: {
          word_id: string;
          meaning: string;
          part_of_speech: string;
          example: string;
        }[];
        applied?: boolean;
      }[]
    >("/word-suggestions");
  const visible = words.data?.items || [];
  function reload() {
    words.reload();
    suggestions.reload();
  }
  async function enqueue(kind: string) {
    setBusy(true);
    setError("");
    try {
      const keys = selected.length
        ? selected
        : visible.slice(0, 10).map((w) => w.id);
      if (!keys.length) throw new Error("先添加或选择一些单词");
      const job = await post<Job>("/jobs", {
        kind,
        payload: { word_ids: keys, mode, direction },
      });
      setJobRevision((x) => x + 1);
      setNotice("已提交，题目或词义整理完成后会出现在下方");
      if (kind === "quiz") router.replace(`/words?quiz=${job.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="WORDS BECOME YOURS"
        title="读到的词，慢慢记住。"
        description="把生词收进来，在语境和练习中真正掌握它。"
      >
        <button className="button" onClick={() => setEditing("new")}>
          ＋ 添加生词
        </button>
      </PageHeading>
      <div className="word-toolbar">
        <form
          className="search-form"
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            router.replace(`/words?q=${encodeURIComponent(search)}`);
          }}
        >
          <label className="sr-only" htmlFor="word-search">
            搜索单词、释义或标签
          </label>
          <input
            id="word-search"
            name="q"
            placeholder="搜索单词、释义或标签…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="button secondary">搜索</button>
        </form>
        <label className="button secondary upload-label">
          导入 CSV
          <input
            type="file"
            accept=".csv"
            aria-label="导入词汇 CSV"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              try {
                const form = new FormData();
                form.append("file", file);
                const response = await fetch("/api/v1/words/import", {
                  method: "POST",
                  body: form,
                });
                const value = await response.json();
                if (!response.ok) throw new Error(value.detail);
                setNotice(
                  `已导入 ${value.imported} 个，跳过重复词 ${value.skipped} 个`,
                );
                reload();
              } catch (err) {
                setError((err as Error).message);
              }
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <p className="muted small-text">
        CSV 列名：term, meaning, example, tags；使用 UTF-8
        编码。重复单词请编辑原词条补充词义。
      </p>
      <nav className="filter-tabs" aria-label="词汇筛选">
        {[
          ["all", "全部词汇"],
          ["due", "到期复习"],
          ["wrong", "易错词汇"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={filter === key ? "active" : ""}
            onClick={() => {
              setFilter(key);
              setOffset(0);
            }}
          >
            {label}
          </button>
        ))}
      </nav>
      <Notice text={error || words.error} error />
      <Notice text={notice} />
      <section className="practice-bar">
        <div>
          <strong>选词强化</strong>
          <small>已选 {selected.length} 个；不选则练习当前列表前 10 个</small>
        </div>
        <label>
          <span className="sr-only">练习题型</span>
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="dictation">单词默写</option>
            <option value="translation">句子翻译</option>
            <option value="choice">词义辨析</option>
          </select>
        </label>
        {mode === "translation" ? (
          <label>
            <span className="sr-only">翻译方向</span>
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
            >
              <option value="zh-en">中译英</option>
              <option value="en-zh">英译中</option>
            </select>
          </label>
        ) : null}
        <button
          className="button"
          disabled={busy}
          onClick={() => enqueue("quiz")}
        >
          开始练习 →
        </button>
        <button
          className="button secondary"
          disabled={busy}
          onClick={() => enqueue("word_enrich")}
        >
          AI 补全词义
        </button>
      </section>
      {words.loading && !words.data ? <Loading /> : null}
      {visible.length ? (
        <div className="word-list">
          {visible.map((w) => (
            <article key={w.id} className="word-row">
              <label className="select-word">
                <input
                  type="checkbox"
                  checked={selected.includes(w.id)}
                  disabled={!selected.includes(w.id) && selected.length >= 20}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, w.id]
                        : selected.filter((x) => x !== w.id),
                    )
                  }
                  aria-label={`选择 ${w.term}`}
                />
              </label>
              <div className="word-main">
                <h2 lang="en">
                  {w.term}
                  <small>{w.part_of_speech}</small>
                </h2>
                <p>{w.meaning || "还没有释义，点击编辑或让 AI 补全。"}</p>
                {w.example ? (
                  <p lang="en" className="word-example">
                    {w.example}
                  </p>
                ) : null}
                <div className="word-meta">
                  <span>{w.tags || "个人生词"}</span>
                  <span>复习：{w.review_on}</span>
                  <span>答错 {w.wrong_count} 次</span>
                </div>
              </div>
              <div className="word-controls">
                <span
                  className="mastery"
                  aria-label={`掌握阶段 ${w.stage} / 6`}
                >
                  {Array.from({ length: 6 }, (_, i) => (
                    <i key={i} className={i < w.stage ? "filled" : ""} />
                  ))}
                </span>
                <button
                  className="button small secondary"
                  onClick={() => setEditing(w)}
                >
                  编辑词条
                </button>
                <button
                  className="button small quiet"
                  onClick={async () => {
                    try {
                      await post(`/words/${w.id}/review`, { correct: true });
                      reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  已掌握
                </button>
                <button
                  className="button small quiet"
                  onClick={async () => {
                    try {
                      await post(`/words/${w.id}/review`, { correct: false });
                      reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  重新复习
                </button>
                <button
                  className="button small quiet"
                  onClick={async () => {
                    if (!confirm(`删除生词 ${w.term}？`)) return;
                    try {
                      await request(
                        `/records/words/${w.id}?version=${w.version}`,
                        { method: "DELETE" },
                      );
                      setSelected(selected.filter((id) => id !== w.id));
                      reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : !words.loading ? (
        <Empty title="从遇见的第一个生词开始">
          手动添加，或阅读新闻时把感兴趣的词收进来。
        </Empty>
      ) : null}
      <Pagination
        offset={offset}
        total={words.data?.total || 0}
        onChange={setOffset}
      />
      {suggestions.data
        ?.filter((s) => !s.applied)
        .map((s) => (
          <section className="draft-panel" key={s.id}>
            <h3>AI 词义补全 · 核对后采用</h3>
            {s.words.map((w) => (
              <div key={w.word_id}>
                <strong>
                  {words.data?.items.find((x) => x.id === w.word_id)?.term}
                </strong>
                <p>
                  {w.part_of_speech} · {w.meaning}
                </p>
                <p lang="en">{w.example}</p>
              </div>
            ))}
            <button
              className="button"
              onClick={async () => {
                try {
                  await post(`/word-suggestions/${s.id}/adoption`, {
                    version: s.version,
                    data: {},
                  });
                  reload();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              采用词义补全
            </button>
          </section>
        ))}
      {quiz ? <Quiz key={quiz} id={quiz} onChanged={words.reload} /> : null}
      <JobPanel refreshKey={jobRevision} onFinished={reload} />
      {editing ? (
        <RecordForm
          title={editing === "new" ? "添加生词" : "编辑词条"}
          fields={wordFields}
          initial={editing === "new" ? {} : { ...editing }}
          onClose={() => setEditing(null)}
          onSave={async (data) => {
            if (editing === "new") await post("/records/words", data);
            else
              await put(`/records/words/${editing.id}`, {
                version: editing.version,
                data,
              });
            reload();
          }}
        />
      ) : null}
    </>
  );
}
