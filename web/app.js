/* Gacha Dailies -- phone front-end.
 *
 * All facts (tasks, reset schedules, events, pull verdicts) are baked into
 * web/data/*.json by build_web.py, which runs the same Python scrapers the
 * desktop app uses. Nothing is scraped from the browser -- those sites send
 * no CORS headers, so a page can't read them directly even if we wanted to.
 *
 * Checklist ticks live in this device's localStorage (per the "separate per
 * device" choice) and auto-clear at each game's real reset time.
 */
'use strict';

const STORE_KEY = 'gdt.checklist.v1';
const TAB_KEY = 'gdt.tab';

const state = { games: [], events: {}, verdicts: {}, generated: null, tab: 'today' };

/* ------------------------------------------------------------------ utils */
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

function fmtMinutes(total) {
  if (total < 60) return `${total} min`;
  const h = Math.floor(total / 60), m = total % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function fmtCountdown(target) {
  let secs = Math.max(0, Math.floor((target - new Date()) / 1000));
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h`;
  return `${h}h ${m}m`;
}

/* ---------------------------------------------------------- reset windows */
/* Ports data/state.py. Python's weekday() is Mon=0..Sun=6 while JS
   getUTCDay() is Sun=0..Sat=6, hence the conversion below. */
function lastDailyReset(reset, now) {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(),
                              reset.daily_hour_utc, 0, 0, 0));
  if (d > now) d.setUTCDate(d.getUTCDate() - 1);
  return d;
}

function lastWeeklyReset(reset, now) {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(),
                              reset.weekly_hour_utc, 0, 0, 0));
  const pyWeekday = (d.getUTCDay() + 6) % 7;
  const daysSince = ((pyWeekday - reset.weekly_weekday) % 7 + 7) % 7;
  d.setUTCDate(d.getUTCDate() - daysSince);
  if (d > now) d.setUTCDate(d.getUTCDate() - 7);
  return d;
}

/* ---------------------------------------------------------------- storage */
function loadStore() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; }
  catch { return {}; }
}
let store = loadStore();

function isDone(taskId, reset, period) {
  const stamp = store[taskId];
  if (!stamp) return false;
  const now = new Date();
  const boundary = period === 'daily' ? lastDailyReset(reset, now) : lastWeeklyReset(reset, now);
  return new Date(stamp) >= boundary;
}

function setDone(taskId, done) {
  if (done) store[taskId] = new Date().toISOString();
  else delete store[taskId];
  localStorage.setItem(STORE_KEY, JSON.stringify(store));
}

/* ------------------------------------------------------------------ data */
async function loadData() {
  const bust = `?v=${Date.now()}`;
  const [games, events, consensus] = await Promise.all([
    fetch(`data/games.json${bust}`).then(r => r.json()),
    fetch(`data/events.json${bust}`).then(r => r.json()),
    fetch(`data/consensus.json${bust}`).then(r => r.json()),
  ]);
  state.games = games.games;
  state.events = events.games;
  state.verdicts = consensus.verdicts;
  state.generated = events.generated_at;
}

function normalizeName(s) {
  return (s || '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}
const prettyTitle = (s) => (s || '').replace(' -- ', ' – ');

/* ------------------------------------------------------------- components */
function sectionHead(title, count, accent) {
  const head = el('div', 'section-head');
  const tick = el('span', 'tick');
  if (accent) tick.style.background = accent;
  head.append(tick, el('h2', null, title));
  if (count != null) head.append(el('span', 'count', String(count)));
  return head;
}

function progressBlock(done, total, caption, value, accent) {
  const wrap = el('div');
  const top = el('div', 'prog-top');
  top.append(el('span', 'cap', caption));
  const val = el('span', 'val', value);
  const complete = total > 0 && done >= total;
  if (complete) val.style.color = 'var(--green)';
  top.append(val);
  const bar = el('div', 'bar');
  const fill = el('i');
  fill.style.width = `${total ? Math.round(100 * done / total) : 0}%`;
  fill.style.background = complete ? 'var(--green)' : (accent || 'var(--accent)');
  bar.append(fill);
  wrap.append(top, bar);
  return wrap;
}

const CHECK_SVG =
  '<svg viewBox="0 0 16 16" fill="none" stroke="#fff" stroke-width="2.6" ' +
  'stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 8.3l3.2 3.2 6.4-7"/></svg>';

function taskRow(game, task, onChange) {
  const row = el('div', 'task');
  row.dataset.done = isDone(task.id, game.reset, task.period) ? '1' : '0';
  const box = el('div', 'box');
  box.innerHTML = CHECK_SVG;
  const label = el('span', 'label', task.label);
  if (task.note) row.title = task.note;
  row.append(box, label, el('span', 'mins', `~${task.minutes}m`));
  row.addEventListener('click', () => {
    const nowDone = row.dataset.done !== '1';
    row.dataset.done = nowDone ? '1' : '0';
    setDone(task.id, nowDone);
    onChange();
  });
  return row;
}

function eventRow(ev, accent, gameIcon) {
  const row = el('div', 'ev');
  const img = el('img');
  img.src = ev.image || gameIcon;
  img.alt = '';
  img.loading = 'lazy';
  img.onerror = () => { img.src = gameIcon; };
  const body = el('div', 'body');
  body.append(el('div', 't', prettyTitle(ev.title)),
              el('div', 'd', ev.when || 'date to be confirmed'));
  const isBanner = ev.category === 'banner';
  const pill = el('span', 'pill', isBanner ? 'BANNER' : 'EVENT');
  pill.style.color = isBanner ? accent : 'var(--faint)';
  pill.style.background = 'var(--surface-alt)';
  row.append(img, body, pill);
  return row;
}

function eventsCard(title, list, accent, gameIcon, emptyMsg, limit) {
  const card = el('section', 'card');
  card.append(sectionHead(title, list.length, accent));
  if (!list.length) { card.append(el('p', 'empty', emptyMsg)); return card; }
  const shown = limit ? list.slice(0, limit) : list;
  shown.forEach(ev => card.append(eventRow(ev, accent, gameIcon)));
  if (shown.length < list.length) {
    card.append(el('p', 'empty', `+${list.length - shown.length} more`));
  }
  return card;
}

/* ------------------------------------------------------------- today view */
function renderToday(view) {
  let remaining = 0, totalMins = 0, doneCount = 0, taskCount = 0;
  state.games.forEach(g => g.tasks.forEach(t => {
    totalMins += t.minutes; taskCount++;
    if (isDone(t.id, g.reset, t.period)) doneCount++; else remaining += t.minutes;
  }));

  const liveCount = state.games.reduce(
    (n, g) => n + ((state.events[g.id] || {}).current || []).length, 0);

  const stats = el('div', 'stats');
  const tiles = [
    [fmtMinutes(remaining), 'time left today', remaining === 0 ? 'var(--green)' : 'var(--text)'],
    [`${doneCount}/${taskCount}`, 'tasks done', 'var(--accent)'],
    [String(liveCount), 'events live', 'var(--blue)'],
    [String(state.games.length), 'games tracked', 'var(--amber)'],
  ];
  tiles.forEach(([v, k, c]) => {
    const t = el('div', 'stat');
    const val = el('div', 'v', v); val.style.color = c;
    t.append(val, el('div', 'k', k));
    stats.append(t);
  });
  view.append(stats);

  // progress per game
  const prog = el('section', 'card');
  prog.append(sectionHead('Progress by game', null, 'var(--accent)'));
  state.games.forEach((g, i) => {
    if (i) prog.append(el('div', 'divider'));
    const done = g.tasks.filter(t => isDone(t.id, g.reset, t.period)).length;
    const left = g.tasks.filter(t => !isDone(t.id, g.reset, t.period))
                        .reduce((s, t) => s + t.minutes, 0);
    prog.append(progressBlock(done, g.tasks.length,
      `${g.name} — ${done}/${g.tasks.length}`,
      left === 0 ? 'done' : `${fmtMinutes(left)} left`, g.accent));
  });
  view.append(prog);

  // still to do
  const pending = [];
  state.games.forEach(g => g.tasks.forEach(t => {
    if (!isDone(t.id, g.reset, t.period)) pending.push([g, t]);
  }));
  const todo = el('section', 'card');
  todo.append(sectionHead('Still to do', pending.length, 'var(--amber)'));
  if (!pending.length) {
    todo.append(el('p', 'empty', "Everything's checked off. Nice work."));
  } else {
    const shown = pending.slice(0, 14);
    let lastGame = null;
    shown.forEach(([g, t]) => {
      if (g !== lastGame) {
        lastGame = g;
        const h = el('div', 'grp', g.name);
        h.style.color = g.accent;
        todo.append(h);
      }
      const row = el('div', 'todo');
      const tag = el('span', 'tag', t.period === 'daily' ? 'D' : 'W');
      tag.style.background = 'var(--surface-alt)';
      tag.style.color = t.period === 'daily' ? 'var(--accent)' : 'var(--blue)';
      row.append(tag, el('span', null, t.label), el('span', 'mins', `~${t.minutes}m`));
      row.querySelector('span:nth-child(2)').style.flex = '1';
      row.querySelector('.mins').style.color = 'var(--faint)';
      row.querySelector('.mins').style.fontSize = '12px';
      todo.append(row);
    });
    if (pending.length > shown.length) {
      todo.append(el('p', 'empty', `+${pending.length - shown.length} more — see the game tabs`));
    }
  }
  view.append(todo);

  // cross-game events
  const live = [], soon = [];
  state.games.forEach(g => {
    const ev = state.events[g.id] || {};
    (ev.current || []).forEach(e => live.push({ ...e, _g: g }));
    (ev.upcoming || []).forEach(e => soon.push({ ...e, _g: g }));
  });
  live.sort((a, b) => (a.end || '9999') > (b.end || '9999') ? 1 : -1);
  soon.sort((a, b) => (a.start || '9999') > (b.start || '9999') ? 1 : -1);

  [['Live now', live], ['Coming up', soon]].forEach(([title, list]) => {
    const card = el('section', 'card');
    card.append(sectionHead(title, list.length, 'var(--blue)'));
    if (!list.length) card.append(el('p', 'empty', 'Nothing here yet.'));
    list.slice(0, 12).forEach(e => card.append(eventRow(e, e._g.accent, e._g.icon)));
    if (list.length > 12) card.append(el('p', 'empty', `+${list.length - 12} more`));
    view.append(card);
  });
}

/* -------------------------------------------------------------- game view */
function renderGame(view, game) {
  const ev = state.events[game.id] || { current: [], upcoming: [] };

  const hero = el('section', 'card');
  const top = el('div', 'hero-top');
  const icon = el('img'); icon.src = game.icon; icon.alt = '';
  const titles = el('div');
  titles.append(el('h2', null, game.name), el('p', null, game.reset.tz_note));
  top.append(icon, titles);
  hero.append(top);

  const now = new Date();
  const nextDaily = new Date(lastDailyReset(game.reset, now).getTime() + 864e5);
  const nextWeekly = new Date(lastWeeklyReset(game.reset, now).getTime() + 7 * 864e5);
  const chips = el('div', 'chips');
  chips.append(el('span', 'chip', `Daily reset in ${fmtCountdown(nextDaily)}`),
               el('span', 'chip', `Weekly reset in ${fmtCountdown(nextWeekly)}`));
  hero.append(chips);

  const progHost = el('div');
  hero.append(progHost);

  const guideBtn = el('button', 'btn', 'Banner Guide — should you pull?');
  guideBtn.addEventListener('click', () => openGuide(game));
  hero.append(guideBtn);
  view.append(hero);

  const update = () => {
    const done = game.tasks.filter(t => isDone(t.id, game.reset, t.period)).length;
    const left = game.tasks.filter(t => !isDone(t.id, game.reset, t.period))
                           .reduce((s, t) => s + t.minutes, 0);
    progHost.innerHTML = '';
    progHost.append(progressBlock(done, game.tasks.length,
      left === 0 ? 'All done — go enjoy the games.' : `${done} of ${game.tasks.length} tasks done`,
      `${fmtMinutes(left)} left`, game.accent));
  };
  update();

  [['daily', 'Daily'], ['weekly', 'Weekly']].forEach(([period, title]) => {
    const tasks = game.tasks.filter(t => t.period === period);
    if (!tasks.length) return;
    const card = el('section', 'card');
    const mins = tasks.reduce((s, t) => s + t.minutes, 0);
    card.append(sectionHead(title, `${tasks.length} · ~${fmtMinutes(mins)}`, game.accent));
    tasks.forEach(t => card.append(taskRow(game, t, update)));
    view.append(card);
  });

  view.append(eventsCard('Live now', ev.current, game.accent, game.icon, 'Nothing running right now.'));
  view.append(eventsCard('Coming up', ev.upcoming, game.accent, game.icon, 'Nothing announced yet.'));
}

/* ------------------------------------------------------------ banner guide */
function verdictColor(label) {
  const u = (label || '').toUpperCase();
  if (u.includes('STRONG')) return 'var(--green)';
  if (u.includes('GOOD')) return '#5cc98d';
  if (u.includes('SITUATIONAL')) return 'var(--amber)';
  if (u.includes('SKIP') || u.includes('LOW PRIORITY')) return 'var(--red)';
  return 'var(--faint)';
}

function openGuide(game) {
  const ev = state.events[game.id] || { current: [], upcoming: [] };
  const banners = [...ev.current, ...ev.upcoming].filter(e => e.category === 'banner');
  $('#sheet-title').textContent = `${game.name} — should you pull?`;
  const body = $('#sheet-body');
  body.innerHTML = '';

  if (!banners.length) {
    body.append(el('p', 'empty', 'No character banners live or announced right now.'));
  }

  banners.forEach(b => {
    const card = el('div', 'bg-card');
    const head = el('div', 'bg-head');
    const img = el('img');
    img.src = b.image || game.icon; img.alt = ''; img.loading = 'lazy';
    img.onerror = () => { img.src = game.icon; };
    const info = el('div');
    info.append(el('div', 't', prettyTitle(b.title)),
                el('div', 'd', b.when || 'date to be confirmed'));
    head.append(img, info);
    card.append(head);

    const v = state.verdicts[`${game.id}:${normalizeName(b.title)}`];
    if (v) {
      const badge = el('span', 'verdict',
        v.score != null ? `${v.label}  ${v.score.toFixed(1)}/5` : v.label);
      badge.style.background = verdictColor(v.label);
      badge.style.color = '#10121a';
      card.append(badge);

      v.sources.forEach(s => {
        const box = el('div', 'src');
        const h = el('div', 'src-head');
        h.append(el('span', 'n', s.name));
        if (s.verdict) {
          const p = el('span', 'pill', s.verdict);
          p.style.color = verdictColor(s.verdict) === 'var(--faint)'
            ? 'var(--dim)' : verdictColor(s.verdict);
          p.style.background = 'var(--surface)';
          h.append(p);
        }
        box.append(h);
        if (s.analysis) box.append(el('p', null, s.analysis));
        [['PROS', s.pros, 'var(--green)'], ['CONS', s.cons, 'var(--red)']].forEach(([t, items, c]) => {
          if (!items || !items.length) return;
          const hh = el('h4', null, t); hh.style.color = c;
          box.append(hh);
          const ul = el('ul');
          items.forEach(i => ul.append(el('li', null, i)));
          box.append(ul);
        });
        if (s.url) {
          const a = el('a', null, 'View source →');
          a.href = s.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
          box.append(a);
        }
        card.append(box);
      });
    } else {
      card.append(el('p', 'empty', 'No pull-verdict data for this banner yet.'));
    }
    body.append(card);
  });

  $('#sheet').hidden = false;
  document.body.style.overflow = 'hidden';
}

function closeGuide() {
  $('#sheet').hidden = true;
  document.body.style.overflow = '';
}

/* ------------------------------------------------------------------ shell */
function renderTabs() {
  const tabs = $('#tabs');
  tabs.innerHTML = '';
  const mk = (id, label, icon) => {
    const b = el('button', 'tab');
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(state.tab === id));
    if (icon) { const i = el('img'); i.src = icon; i.alt = ''; b.append(i); }
    b.append(el('span', null, label));
    b.addEventListener('click', () => {
      state.tab = id;
      localStorage.setItem(TAB_KEY, id);
      render();
      window.scrollTo({ top: 0 });
    });
    return b;
  };
  tabs.append(mk('today', 'Today'));
  state.games.forEach(g => tabs.append(mk(g.id, g.name, g.icon)));
}

function render() {
  renderTabs();
  const view = $('#view');
  view.innerHTML = '';
  if (state.tab === 'today') renderToday(view);
  else {
    const game = state.games.find(g => g.id === state.tab);
    if (game) renderGame(view, game); else renderToday(view);
  }
}

function showUpdated() {
  if (!state.generated) return;
  const d = new Date(state.generated);
  const label = d.toLocaleString(undefined,
    { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  $('#updated').textContent = `Data updated ${label}`;
}

function toast(msg) {
  const t = el('div', 'toast', msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 2600);
}

async function boot() {
  state.tab = localStorage.getItem(TAB_KEY) || 'today';
  try {
    await loadData();
    showUpdated();
    render();
  } catch (err) {
    $('#updated').textContent = 'Could not load data';
    $('#view').append(el('p', 'empty', 'No data available yet. Check your connection and reload.'));
    console.error(err);
  }

  $('#reload').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.classList.add('spin');
    try {
      await loadData();
      showUpdated();
      render();
      toast('Up to date');
    } catch {
      toast('Offline — showing saved data');
    } finally {
      btn.classList.remove('spin');
    }
  });

  document.querySelectorAll('[data-close]').forEach(n => n.addEventListener('click', closeGuide));
  window.addEventListener('keydown', e => { if (e.key === 'Escape') closeGuide(); });

  // countdowns drift as the minutes tick over
  setInterval(() => { if (state.tab !== 'today') render(); }, 60000);

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
}

boot();
