from flask import Flask, jsonify, render_template_string
from database import Database
import os
from datetime import datetime

app = Flask(__name__)
db = Database()

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BALO — Classement 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,100..900&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:      #0a0a0a;
  --surface: #111111;
  --ink:     #ffffff;
  --muted:   #555555;
  --rule:    #1e1e1e;
  --hover:   #161616;
  --active:  #ffffff;
  --pill-bg: #ffffff;
  --pill-fg: #000000;
}

html { scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--ink);
  font-family: 'Inter', sans-serif;
  min-height: 100vh;
}

/* ── HEADER ── */
header {
  padding: 52px 64px 40px;
  border-bottom: 1px solid var(--rule);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.header-title {
  font-size: clamp(42px, 6.5vw, 76px);
  font-weight: 900;
  line-height: 0.92;
  letter-spacing: -3px;
  text-transform: uppercase;
  color: var(--ink);
}

.header-meta {
  text-align: right;
  flex-shrink: 0;
  padding-bottom: 4px;
}

.header-meta .eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--muted);
  display: block;
  margin-bottom: 6px;
}

.header-meta .desc {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
  max-width: 200px;
}

/* ── STATS ── */
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid var(--rule);
}

.stat {
  padding: 28px 64px;
  border-right: 1px solid var(--rule);
}
.stat:last-child { border-right: none; }

.stat-value {
  font-size: 38px;
  font-weight: 900;
  letter-spacing: -2px;
  line-height: 1;
  color: var(--ink);
}

.stat-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: var(--muted);
  margin-top: 7px;
}

/* ── SORT TABS ── */
.sort-bar {
  padding: 28px 64px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sort-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
  margin-right: 8px;
  flex-shrink: 0;
}

.sort-btn {
  font-family: 'Inter', sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 7px 16px;
  border-radius: 2px;
  border: 1px solid var(--rule);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: all .15s;
}

.sort-btn:hover {
  border-color: #333;
  color: var(--ink);
}

.sort-btn.active {
  background: var(--pill-bg);
  color: var(--pill-fg);
  border-color: var(--pill-bg);
}

/* ── TABLE ── */
.table-wrap { padding: 24px 64px 80px; }

/* rang | nom | victoires | participations | streak */
.grid5 {
  display: grid;
  grid-template-columns: 52px 1fr 120px 145px 110px;
  align-items: center;
}

.thead {
  border-bottom: 1px solid #2a2a2a;
  padding-bottom: 10px;
  margin-bottom: 4px;
}

.thead span {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
  user-select: none;
}

.thead .r { text-align: right; }

.thead .sortable {
  cursor: pointer;
  transition: color .15s;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
}
.thead .sortable:hover { color: var(--ink); }
.thead .sortable.active { color: var(--ink); }

.sort-arrow {
  font-size: 8px;
  opacity: 0;
  transition: opacity .15s;
}
.thead .sortable.active .sort-arrow { opacity: 1; }

/* ROWS */
#rows-container { position: relative; }

.trow {
  border-bottom: 1px solid var(--rule);
  padding: 13px 0;
  transition: background .1s;
  will-change: transform, opacity;
}

.trow:hover { background: var(--hover); }

.c-rank {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  transition: color .2s;
}
.c-rank.r1 { font-size: 14px; font-weight: 900; color: var(--ink); }
.c-rank.r2, .c-rank.r3 { font-weight: 700; color: #666; }

.c-name {
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding-right: 16px;
  color: var(--ink);
}

.c-name .uname {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fire-pill {
  flex-shrink: 0;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .5px;
  background: var(--ink);
  color: var(--bg);
  border-radius: 2px;
  padding: 2px 6px;
}

.c-num {
  font-size: 14px;
  font-weight: 500;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  transition: color .2s, font-weight .2s;
}
.c-num.highlight { font-weight: 800; font-size: 15px; }
.c-num.dim       { color: var(--muted); font-weight: 400; }

.empty {
  padding: 64px 0;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
}

/* ── FOOTER ── */
footer {
  border-top: 1px solid var(--rule);
  padding: 18px 64px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
footer span {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
}
footer .footer-note {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.5px;
  text-transform: none;
  color: var(--muted);
  text-align: center;
  flex: 1;
}

/* ── RESPONSIVE ── */
@media (max-width: 720px) {
  header { padding: 28px 20px 24px; flex-direction: column; align-items: flex-start; }
  .header-meta { text-align: left; }
  .header-meta .desc { max-width: 100%; }
  .stats { grid-template-columns: 1fr 1fr; }
  .stat { padding: 18px 20px; }
  .stat:nth-child(3) { grid-column: 1/-1; border-right: none; border-top: 1px solid var(--rule); }
  .sort-bar { padding: 20px 20px 0; flex-wrap: wrap; }
  .table-wrap { padding: 16px 20px 48px; }
  .grid5 { grid-template-columns: 36px 1fr 72px 84px; }
  .col-streak { display: none; }
  .th-streak { display: none !important; }
  footer { padding: 14px 20px; }
}
</style>
</head>
<body>

<header>
  <div class="header-title">Bataille<br>de Logos</div>
  <div class="header-meta">
    <span class="eyebrow">Classement général 2026</span>
    <span class="desc">Serveur BALO — clique sur une colonne pour trier.</span>
  </div>
</header>

<div class="stats">
  <div class="stat">
    <div class="stat-value">{{ total_battles }}</div>
    <div class="stat-label">Batailles</div>
  </div>
  <div class="stat">
    <div class="stat-value">{{ total_players }}</div>
    <div class="stat-label">Participants</div>
  </div>
  <div class="stat">
    <div class="stat-value">{{ total_participations }}</div>
    <div class="stat-label">Soumissions</div>
  </div>
</div>

<div class="sort-bar">
  <span class="sort-label">Trier par</span>
  <button class="sort-btn active" data-sort="victories">Victoires</button>
  <button class="sort-btn" data-sort="participations">Participations</button>
  <button class="sort-btn" data-sort="current_streak">Streak actif</button>
</div>

<div class="table-wrap">
  <div class="grid5 thead">
    <span>#</span>
    <span>Joueur</span>
    <span class="r sortable th-victories active" data-sort="victories">
      Victoires <span class="sort-arrow">▼</span>
    </span>
    <span class="r sortable th-participations" data-sort="participations">
      Participations <span class="sort-arrow">▼</span>
    </span>
    <span class="r sortable th-streak th-streak col-streak" data-sort="current_streak">
      Streak <span class="sort-arrow">▼</span>
    </span>
  </div>

  <div id="rows-container">
    {% if players %}
      {% for p in players %}
      <div class="grid5 trow"
           data-victories="{{ p.victories }}"
           data-participations="{{ p.participations }}"
           data-streak="{{ p.current_streak }}"
           data-best="{{ p.best_streak }}"
           data-name="{{ p.username }}"
           data-fire="{{ p.current_streak }}">
        <div class="c-rank"></div>
        <div class="c-name">
          <span class="uname">{{ p.username }}</span>
          {% if p.current_streak >= 2 %}
          <span class="fire-pill">🔥 {{ p.current_streak }}</span>
          {% endif %}
        </div>
        <div class="c-num col-victories">{{ p.victories }}</div>
        <div class="c-num col-participations dim">{{ p.participations }}</div>
        <div class="c-num col-streak">{{ p.best_streak }}</div>
      </div>
      {% endfor %}
    {% else %}
      <div class="empty">Aucune donnée disponible pour l'instant.</div>
    {% endif %}
  </div>
</div>

<footer>
  <span>Le Héraut · BALO</span>
  <span class="footer-note">* Le mode streamer peut fausser certaines données du classement</span>
  <span>{{ year }}</span>
</footer>

<script>
// ── DATA ──────────────────────────────────────────────────────────────────
const container = document.getElementById('rows-container');
const rows = Array.from(container.querySelectorAll('.trow'));
let currentSort = 'victories';

// ── SORT ──────────────────────────────────────────────────────────────────
function sortRows(key) {
  currentSort = key;

  // Trie les lignes
  rows.sort((a, b) => {
    const va = parseInt(a.dataset[key === 'current_streak' ? 'streak' : key]) || 0;
    const vb = parseInt(b.dataset[key === 'current_streak' ? 'streak' : key]) || 0;
    if (vb !== va) return vb - va;
    // Départage secondaire
    if (key === 'victories')       return parseInt(b.dataset.participations) - parseInt(a.dataset.participations);
    if (key === 'participations')  return parseInt(b.dataset.victories) - parseInt(a.dataset.victories);
    return parseInt(b.dataset.victories) - parseInt(a.dataset.victories);
  });

  // Anime la transition
  rows.forEach((row, i) => {
    row.style.transition = 'none';
    row.style.opacity = '0';
    row.style.transform = 'translateY(8px)';
  });

  rows.forEach(row => container.appendChild(row));

  // Met à jour les rangs et highlights
  rows.forEach((row, i) => {
    const rank = row.querySelector('.c-rank');
    const n = i + 1;
    rank.textContent = n;
    rank.className = 'c-rank' + (n === 1 ? ' r1' : n === 2 ? ' r2' : n === 3 ? ' r3' : '');

    // Highlight la colonne active
    const v = row.querySelector('.col-victories');
    const p = row.querySelector('.col-participations');
    const s = row.querySelector('.col-streak');

    v.className = 'c-num col-victories' + (key === 'victories' ? ' highlight' : ' dim');
    p.className = 'c-num col-participations' + (key === 'participations' ? ' highlight' : ' dim');
    s.className = 'c-num col-streak' + (key === 'current_streak' ? ' highlight' : ' dim');

    // Fade in avec délai décalé
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        row.style.transition = `opacity .3s ${i * 0.02}s, transform .3s ${i * 0.02}s`;
        row.style.opacity = '1';
        row.style.transform = 'none';
      });
    });
  });

  updateActiveUI(key);
}

// ── UI ACTIVE STATE ────────────────────────────────────────────────────────
function updateActiveUI(key) {
  // Boutons
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.sort === key);
  });

  // En-têtes
  document.querySelectorAll('.thead .sortable').forEach(th => {
    th.classList.toggle('active', th.dataset.sort === key);
  });
}

// ── EVENTS ────────────────────────────────────────────────────────────────
document.querySelectorAll('.sort-btn').forEach(btn => {
  btn.addEventListener('click', () => sortRows(btn.dataset.sort));
});

document.querySelectorAll('.thead .sortable').forEach(th => {
  th.addEventListener('click', () => sortRows(th.dataset.sort));
});

// ── INIT ──────────────────────────────────────────────────────────────────
// Applique l'état initial (victoires) + animation d'entrée
rows.forEach((row, i) => {
  row.style.opacity = '0';
  row.style.transform = 'translateY(10px)';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      row.style.transition = `opacity .4s ${i * 0.025}s, transform .4s ${i * 0.025}s`;
      row.style.opacity = '1';
      row.style.transform = 'none';
    });
  });
  // Rangs initiaux déjà corrects (triés côté serveur par victoires)
  const rank = row.querySelector('.c-rank');
  const n = i + 1;
  rank.textContent = n;
  rank.className = 'c-rank' + (n === 1 ? ' r1' : n === 2 ? ' r2' : n === 3 ? ' r3' : '');
});
</script>

</body>
</html>"""


@app.route("/")
def leaderboard():
    players = db.get_all_stats()
    total_battles = db.get_total_battles()
    total_players = len(players)
    total_participations = sum(p["participations"] for p in players)
    return render_template_string(
        HTML_TEMPLATE,
        players=players,
        total_battles=total_battles,
        total_players=total_players,
        total_participations=total_participations,
        year=datetime.now().year
    )


@app.route("/api/leaderboard")
def api_leaderboard():
    """Endpoint JSON pour une future app mobile."""
    players = db.get_all_stats()
    return jsonify({
        "total_battles": db.get_total_battles(),
        "players": players,
        "recent_battles": db.get_recent_battles(10)
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
