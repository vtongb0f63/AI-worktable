import type { Node } from '@/lib/api';

type TreeNode = Pick<Node, 'id' | 'parent_id' | 'kind' | 'title' | 'progress'>;

export default function TreeGraphic({ nodes, compact = false }: { nodes: TreeNode[]; compact?: boolean }) {
  const years = nodes.filter(n => n.kind === 'year').slice(0, 4);
  const tasks = nodes.filter(n => n.kind === 'task').slice(0, 42);
  const milestones = nodes.filter(n => n.kind === 'month').slice(0, 18);
  const positions = years.map((year, index) => ({ year, x: 90 + index * 175, y: 197 - (index % 2) * 25 }));
  const ancestorYear = (node: TreeNode) => {
    let current = node;
    for (let i = 0; i < 5; i++) {
      if (current.kind === 'year') return current.id;
      const parent = nodes.find(x => x.id === current.parent_id);
      if (!parent) break;
      current = parent;
    }
    return null;
  };
  return <svg viewBox="0 0 700 340" role="img" aria-label="成长树：枝条代表学年，叶子代表任务" style={{ width: '100%', maxHeight: compact ? 260 : 400, overflow: 'visible' }}>
    <defs>
      <linearGradient id="trunk" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#72879d"/><stop offset="1" stopColor="#36577e"/></linearGradient>
    </defs>
    <path d="M350 327 Q338 263 350 149" stroke="url(#trunk)" strokeWidth="18" fill="none" strokeLinecap="round"/>
    <path d="M350 315 Q324 332 307 339 M350 313 Q380 327 394 339" stroke="#56708d" strokeWidth="8" fill="none" strokeLinecap="round"/>
    {positions.map(({ year, x, y }, index) => <g key={year.id}>
      <path d={`M350 165 Q${(350+x)/2} ${y-35} ${x} ${y}`} fill="none" stroke="#68839f" strokeWidth="${7-index}" strokeLinecap="round"/>
      <circle cx={x} cy={y} r="17" fill={year.progress > 0 ? '#d8eee3' : '#e9eef5'} stroke={year.progress > 0 ? '#63a889' : '#a9bfd4'} strokeWidth="2"/>
      <text x={x} y={y+4} textAnchor="middle" fill="#294b6b" fontSize="12" fontWeight="700">{index + 1}</text>
      <text x={x} y={y+37} textAnchor="middle" fill="#526c84" fontSize="13">{year.title.slice(0, 8)}</text>
    </g>)}
    {milestones.map((milestone, index) => {
      const parent = positions.find(p => p.year.id === ancestorYear(milestone));
      if (!parent) return null;
      const same = milestones.filter(m => ancestorYear(m) === parent.year.id);
      const local = same.findIndex(m => m.id === milestone.id);
      const angle = -Math.PI + (local + 1) * Math.PI / (same.length + 1);
      const x = parent.x + Math.cos(angle) * 58;
      const y = parent.y + Math.sin(angle) * 56;
      return <g key={milestone.id}><path d={`M${parent.x} ${parent.y} Q${(parent.x+x)/2} ${y+15} ${x} ${y}`} stroke="#8ca9b5" strokeWidth="2" fill="none"/><circle cx={x} cy={y} r={milestone.progress >= 100 ? 9 : 5} fill={milestone.progress >= 100 ? '#e5ae5a' : '#b3c8d4'}/>{milestone.progress >= 100 && <circle cx={x} cy={y} r="3" fill="#fff5da"/>}</g>;
    })}
    {tasks.map((task, index) => {
      const parent = positions.find(p => p.year.id === ancestorYear(task));
      if (!parent) return null;
      const same = tasks.filter(t => ancestorYear(t) === parent.year.id);
      const local = same.findIndex(t => t.id === task.id);
      const angle = -Math.PI + (local + 1) * Math.PI / (same.length + 1);
      const radius = 95 + (local % 3) * 15;
      const x = parent.x + Math.cos(angle) * radius;
      const y = parent.y + Math.sin(angle) * (radius * .8);
      return <g key={task.id}><path d={`M${parent.x} ${parent.y} Q${(parent.x+x)/2} ${y+12} ${x} ${y}`} stroke="#9aafba" strokeWidth="1.5" fill="none"/><ellipse cx={x} cy={y} rx="8" ry="13" transform={`rotate(${angle*180/Math.PI+90} ${x} ${y})`} fill={task.progress >= 100 ? '#5fa588' : '#cfdae1'}><title>{task.title}</title></ellipse></g>;
    })}
    {!years.length && <text x="350" y="110" textAnchor="middle" fill="#738da5" fontSize="18">建立学年目标后，枝条会从这里长出</text>}
  </svg>;
}
