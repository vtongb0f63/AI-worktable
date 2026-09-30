export default function SproutAnimation() {
  return <svg className="sprout-illustration" viewBox="0 0 500 350" role="img"
    aria-label="一株三叶草从土里发芽，三片叶子逐渐舒展开并由黑色变为绿色">
    <defs>
      <linearGradient id="sprout-growth" x1="0" y1="1" x2=".7" y2="0">
        <stop offset="0" stopColor="#171b13"/>
        <stop offset=".48" stopColor="#3b6c3c"/>
        <stop offset="1" stopColor="#8bd471"/>
      </linearGradient>
      <linearGradient id="sprout-soil" x1="0" y1="0" x2="0" y2="1">
        <stop stopColor="#b57c4b"/>
        <stop offset="1" stopColor="#493326"/>
      </linearGradient>
    </defs>
    <circle cx="250" cy="158" r="130" fill="#e7d9a7" opacity=".08"/>
    <path className="sprout-stem" d="M250 286 C254 246 242 215 250 180 C258 155 251 139 250 128"
      fill="none" stroke="url(#sprout-growth)" strokeWidth="12" strokeLinecap="round"/>
    <g className="sprout-leaf sprout-leaf-left">
      <path d="M250 166 C210 166 182 137 195 101 C224 94 254 123 250 166 Z"
        fill="url(#sprout-growth)" stroke="#315c36" strokeWidth="2"/>
      <path d="M245 158 Q226 126 204 109" fill="none" stroke="#c5e0a0" strokeWidth="2" opacity=".6"/>
    </g>
    <g className="sprout-leaf sprout-leaf-right">
      <path d="M250 166 C290 166 318 137 305 101 C276 94 246 123 250 166 Z"
        fill="url(#sprout-growth)" stroke="#315c36" strokeWidth="2"/>
      <path d="M255 158 Q274 126 296 109" fill="none" stroke="#c5e0a0" strokeWidth="2" opacity=".6"/>
    </g>
    <g className="sprout-leaf sprout-leaf-top">
      <path d="M250 145 C225 120 226 82 250 64 C274 82 275 120 250 145 Z"
        fill="url(#sprout-growth)" stroke="#315c36" strokeWidth="2"/>
      <path d="M250 136 L250 76" fill="none" stroke="#c5e0a0" strokeWidth="2" opacity=".6"/>
    </g>
    <ellipse cx="250" cy="296" rx="152" ry="29" fill="url(#sprout-soil)"/>
    <path d="M103 295 Q250 267 397 295" fill="none" stroke="#ce9d69" strokeWidth="5" opacity=".8"/>
    <circle cx="149" cy="301" r="3" fill="#d0a376"/><circle cx="342" cy="306" r="2" fill="#d0a376"/>
  </svg>;
}
