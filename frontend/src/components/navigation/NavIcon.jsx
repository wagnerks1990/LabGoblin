const paths = {
  search: <><circle cx='10' cy='10' r='6'/><path d='m15 15 6 6'/></>,
  home: <><path d='M3 10.5 12 3l9 7.5'/><path d='M5 9.5V21h14V9.5M9 21v-7h6v7'/></>,
  monitor: <><rect x='3' y='4' width='18' height='13' rx='2'/><path d='M8 21h8m-4-4v4'/></>,
  plus: <path d='M12 5v14M5 12h14'/>,
  activity: <path d='M3 12h4l2-7 4 14 2-7h6'/>,
  classroom: <><path d='M4 19v-9a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9'/><path d='M2 19h20M8 8V5h8v3'/></>,
  layers: <><path d='m12 3 9 5-9 5-9-5 9-5Z'/><path d='m3 12 9 5 9-5M3 16l9 5 9-5'/></>,
  session: <><circle cx='12' cy='8' r='4'/><path d='M4 21a8 8 0 0 1 16 0'/></>,
  event: <><path d='M6 3v3m12-3v3M4 9h16v12H4V5h16v4'/><path d='m8 15 2 2 5-5'/></>,
  server: <><rect x='3' y='4' width='18' height='6' rx='1'/><rect x='3' y='14' width='18' height='6' rx='1'/><path d='M7 7h.01M7 17h.01'/></>,
  inventory: <><path d='M4 7h16v14H4V7Zm2-4h12l2 4H4l2-4Z'/><path d='M9 11h6'/></>,
  template: <><rect x='3' y='3' width='18' height='18' rx='2'/><path d='M3 9h18M9 9v12'/></>,
  sync: <><path d='M20 7h-5V2'/><path d='M20 7a8 8 0 0 0-14-2M4 17h5v5'/><path d='M4 17a8 8 0 0 0 14 2'/></>,
  organization: <><path d='M3 21h18M6 21V8h12v13M9 5h6v3'/><path d='M9 12h.01M15 12h.01M9 16h.01M15 16h.01'/></>,
  people: <><circle cx='9' cy='8' r='4'/><path d='M2 21a7 7 0 0 1 14 0M16 4a4 4 0 0 1 0 8M17 15a6 6 0 0 1 5 6'/></>,
  group: <><circle cx='8' cy='8' r='3'/><circle cx='17' cy='9' r='3'/><path d='M2 21a6 6 0 0 1 12 0M13 20a5 5 0 0 1 9 0'/></>,
  pulse: <path d='M3 12h4l2-7 4 14 2-7h6'/>,
  wrench: <path d='M14.5 6.5a4 4 0 0 0-5-5l2 2-3 3-2-2a4 4 0 0 0 5 5L20 18l-3 3-8.5-8.5'/>,
  update: <><path d='M20 11a8 8 0 1 0-2.3 5.7'/><path d='M20 4v7h-7'/></>,
  menu: <path d='M4 6h16M4 12h16M4 18h16'/>,
  close: <path d='m6 6 12 12M18 6 6 18'/>,
  collapse: <path d='m15 18-6-6 6-6'/>,
  expand: <path d='m9 18 6-6-6-6'/>,
  user: <><circle cx='12' cy='8' r='4'/><path d='M4 21a8 8 0 0 1 16 0'/></>,
}

export default function NavIcon({ name, className = '' }) {
  return <svg className={`nav-icon ${className}`.trim()} aria-hidden='true' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='1.8' strokeLinecap='round' strokeLinejoin='round'>{paths[name] || paths.activity}</svg>
}
