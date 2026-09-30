import type { Node } from '@/lib/api';

type TreeNode = Pick<Node, 'id' | 'parent_id' | 'kind' | 'title' | 'progress'>;

const yearSpots = [
  { x: 164, y: 218, startX: 354, startY: 278 },
  { x: 284, y: 127, startX: 358, startY: 226 },
  { x: 456, y: 127, startX: 378, startY: 226 },
  { x: 576, y: 218, startX: 382, startY: 278 },
];

export default function TreeGraphic({ nodes, compact = false }: { nodes: TreeNode[]; compact?: boolean }) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const years = nodes.filter(node => node.kind === 'year').slice(0, 4);
  const tasks = nodes.filter(node => node.kind === 'task').slice(0, 40);
  const milestones = nodes.filter(node => node.kind === 'month').slice(0, 20);
  const positions = years.map((year, index) => ({ year, ...yearSpots[index] }));
  const ancestorYear = (node: TreeNode) => {
    let current: TreeNode | undefined = node;
    for (let depth = 0; current && depth < 6; depth++) {
      if (current.kind === 'year') return current.id;
      current = current.parent_id ? byId.get(current.parent_id) : undefined;
    }
    return null;
  };

  return <svg className="growth-tree" viewBox="0 0 740 440" role="img"
    aria-label="卡通成长树：棕色树干代表愿景，主枝代表学年，花朵代表完成的月里程碑，绿叶代表完成的任务"
    style={{ width: '100%', maxHeight: compact ? 270 : 440 }}>
    <defs>
      <linearGradient id="tree-bark" x1="0" y1="0" x2="1" y2="0">
        <stop stopColor="#5b3926"/><stop offset=".5" stopColor="#9b6034"/><stop offset="1" stopColor="#68412a"/>
      </linearGradient>
      <linearGradient id="tree-leaf" x1="0" y1="0" x2=".8" y2="1">
        <stop stopColor="#91c46f"/><stop offset="1" stopColor="#397b42"/>
      </linearGradient>
      <linearGradient id="tree-soil" x1="0" y1="0" x2="0" y2="1">
        <stop stopColor="#b9824f"/><stop offset="1" stopColor="#83552f"/>
      </linearGradient>
    </defs>

    <ellipse cx="370" cy="413" rx="285" ry="18" fill="#e5d5a9" opacity=".7"/>
    <path d="M84 407 Q370 392 656 407 L656 440 H84 Z" fill="url(#tree-soil)"/>
    <path d="M86 407 Q370 391 654 407" fill="none" stroke="#c99c64" strokeWidth="4"/>

    {positions.map(({ year, x, y, startX, startY }) =>
      <path key={year.id} d={`M${startX} ${startY} Q${(startX+x)/2} ${y-15} ${x} ${y}`}
        fill="none" stroke="#754a2c" strokeWidth="12" strokeLinecap="round"/> )}
    <path d="M339 402 C350 344 350 288 349 234 C348 202 358 182 366 168
             C374 186 387 210 387 237 C387 292 390 350 403 402
             Q385 397 370 379 Q358 398 339 402 Z" fill="url(#tree-bark)"/>
    <path d="M363 203 Q355 256 363 314 M379 239 Q375 305 386 364"
      fill="none" stroke="#bc8650" strokeWidth="4" strokeLinecap="round" opacity=".7"/>
    <path d="M350 377 Q324 398 288 411 M388 375 Q419 399 454 411"
      fill="none" stroke="#68412a" strokeWidth="10" strokeLinecap="round"/>

    {positions.map(({ year, x, y }, index) => <g key={year.id}>
      <g fill={year.progress > 0 ? '#8fb774' : '#c7d5a2'}>
        <circle cx={x-29} cy={y+4} r="37"/>
        <circle cx={x+29} cy={y+4} r="37"/>
        <circle cx={x} cy={y-22} r="43"/>
        <circle cx={x} cy={y+18} r="38"/>
      </g>
      <circle cx={x} cy={y} r="21" fill="#fff7de" stroke="#a86f42" strokeWidth="2.5"/>
      <text x={x} y={y+6} textAnchor="middle" fill="#704327" fontSize="17" fontWeight="800">{index+1}</text>
      <text x={x} y={y+80} textAnchor="middle" fill="#59452b" fontSize="14" fontWeight="700">{year.title.slice(0, 8)}</text>
      <title>{year.title}，已完成 {year.progress}%</title>
    </g>)}

    {milestones.map(milestone => {
      const position = positions.find(item => item.year.id === ancestorYear(milestone));
      if (!position) return null;
      const siblings = milestones.filter(item => ancestorYear(item) === position.year.id);
      const index = siblings.findIndex(item => item.id === milestone.id);
      const angle = (index * 2.399 - 1.2);
      const x = position.x + Math.cos(angle) * 46;
      const y = position.y + Math.sin(angle) * 41 - 8;
      return <g key={milestone.id} transform={`translate(${x} ${y})`}>
        {milestone.progress >= 100 ? <>
          <circle cx="-7" cy="0" r="6" fill="#e9a485"/>
          <circle cx="7" cy="0" r="6" fill="#e9a485"/>
          <circle cx="0" cy="-7" r="6" fill="#f3bea0"/>
          <circle cx="0" cy="7" r="6" fill="#d98870"/>
          <circle r="4" fill="#f5d36e"/>
        </> : <circle r="5" fill="#b8754b" stroke="#e9c39a" strokeWidth="2"/>}
        <title>{milestone.title}</title>
      </g>;
    })}

    {tasks.map(task => {
      const position = positions.find(item => item.year.id === ancestorYear(task));
      if (!position) return null;
      const siblings = tasks.filter(item => ancestorYear(item) === position.year.id);
      const index = siblings.findIndex(item => item.id === task.id);
      const angle = index * 2.399 + .7;
      const radius = 37 + (index % 3) * 11;
      const x = position.x + Math.cos(angle) * radius;
      const y = position.y + Math.sin(angle) * radius;
      const rotation = angle * 180 / Math.PI + 45;
      return <g key={task.id}>
        <path d={`M${position.x} ${position.y} L${x} ${y}`} stroke="#8a633d" strokeWidth="1.5"/>
        <ellipse cx={x} cy={y} rx="7" ry="13" transform={`rotate(${rotation} ${x} ${y})`}
          fill={task.progress >= 100 ? 'url(#tree-leaf)' : '#d5dfad'} stroke="#5b8d52" strokeWidth="1">
          <title>{task.title}</title>
        </ellipse>
      </g>;
    })}
    {!years.length && <text x="370" y="95" textAnchor="middle" fill="#76583b" fontSize="18">建立学年目标，枝叶就会慢慢长出来</text>}
  </svg>;
}
