"use client";
import { useEffect, useState } from "react";
import { api, Node, Event, kindLabel } from "@/lib/api";
import { PageHeading, Empty, Notice } from "./Shared";
export default function History() {
  const [nodes, setNodes] = useState<Node[]>([]),
    [events, setEvents] = useState<Event[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Node[]>("/nodes"), api<Event[]>("/events?limit=100")])
      .then(([n, e]) => {
        setNodes(n);
        setEvents(e);
      })
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <PageHeading
        eyebrow="WHERE YOU STARTED"
        title="旧目标，也值得留下。"
        description="保留原工作台的目标与成长记录；有日期的旧任务已经带入新的日程。"
      />
      <Notice text={error} error />
      <section className="paper-panel">
        <h2>历史目标</h2>
        {nodes.length ? (
          nodes.map((node) => (
            <div className="history-row" key={node.id}>
              <span className="tag">{kindLabel[node.kind]}</span>
              <strong>{node.title}</strong>
              <span>
                {node.is_done ? "已完成" : `${Math.round(node.progress)}%`}
              </span>
              {node.note ? <p>{node.note}</p> : null}
            </div>
          ))
        ) : (
          <Empty title="没有旧目标">后续安排可以直接在新的周日程中创建。</Empty>
        )}
      </section>
      <section className="paper-panel">
        <h2>旧版成长记录</h2>
        {events.map((e) => (
          <div className="history-row" key={e.id}>
            <time>
              {new Intl.DateTimeFormat("zh-CN", {
                timeZone: "Asia/Shanghai",
                dateStyle: "medium",
              }).format(new Date(e.occurred_at))}
            </time>
            <span>{e.kind}</span>
            <p>{String(e.detail.title || e.detail.summary || "")}</p>
          </div>
        ))}
      </section>
    </>
  );
}
