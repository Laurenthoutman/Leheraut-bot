from flask import Flask, jsonify, render_template_string
from database import Database
import os

app = Flask(__name__)
db = Database()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BALO — Classement</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --gold:   #F5C842;
    --silver: #C0C0C0;
    --bronze: #CD7F32;
    --bg:     #0D0D0D;
    --surface:#141414;
    --border: #222;
    --text:   #EAEAEA;
    --muted:  #666;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    min-height: 100vh;
    padding: 0 0 80px;
  }

  /* ── HERO ── */
  .hero {
    position: relative;
    padding: 64px 32px 48px;
    text-align: center;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(245,200,66,.15) 0%, transparent 70%);
    pointer-events: none;
  }
  .hero-eyebrow {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 13px;
    letter-spacing: 4px;
    color: var(--gold);
    margin-bottom: 12px;
  }
  .hero-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(52px, 10vw, 96px);
    line-height: 1;
    letter-spacing: 2px;
    background: linear-gradient(135deg, #fff 30%, var(--gold));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .hero-sub {
    margin-top: 12px;
    font-size: 14px;
    color: var(--muted);
    letter-spacing: 1px;
  }

  /* ── STATS BAR ── */
  .stats-bar {
    display: flex;
    justify-content: center;
    gap: 48px;
    padding: 24px 32px;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    margin-bottom: 48px;
  }
  .stat-item { text-align: center; }
  .stat-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 36px;
    color: var(--gold);
    line-height: 1;
  }
  .stat-label {
    font-size: 11px;
    letter-spacing: 2px;
    color: var(--muted);
    text-transform: uppercase;
    margin-top: 4px;
  }

  /* ── TABLE ── */
  .table-wrap {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 20px;
  }
  .table-header {
    display: grid;
    grid-template-columns: 56px 1fr 80px 80px 80px 80px;
    padding: 0 20px 12px;
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
  }
  .row {
    display: grid;
    grid-template-columns: 56px 1fr 80px 80px 80px 80px;
    align-items: center;
    padding: 16px 20px;
    border-radius: 12px;
    margin-bottom: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    transition: transform .15s, border-color .15s;
    animation: fadeUp .4s both;
  }
  .row:hover {
    transform: translateY(-2px);
    border-color: #333;
  }
  .row:nth-child(1) { border-color: rgba(245,200,66,.4); animation-delay: .05s; }
  .row:nth-child(2) { border-color: rgba(192,192,192,.3); animation-delay: .10s; }
  .row:nth-child(3) { border-color: rgba(205,127,50,.3);  animation-delay: .15s; }

  @keyframes fadeUp {
    from { opacity:0; transform: translateY(16px); }
    to   { opacity:1; transform: translateY(0); }
  }

  .rank {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 22px;
    color: var(--muted);
  }
  .rank.gold   { color: var(--gold); }
  .rank.silver { color: var(--silver); }
  .rank.bronze { color: var(--bronze); }

  .username {
    font-size: 15px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .streak-badge {
    font-size: 11px;
    background: rgba(245,200,66,.15);
    border: 1px solid rgba(245,200,66,.3);
    color: var(--gold);
    border-radius: 20px;
    padding: 2px 8px;
    white-space: nowrap;
  }

  .cell {
    font-size: 14px;
    text-align: center;
    color: var(--text);
  }
  .cell.victories {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 20px;
    color: var(--gold);
  }
  .cell.winrate { color: var(--muted); font-size: 13px; }

  /* ── FOOTER ── */
  .footer {
    text-align: center;
    margin-top: 64px;
    font-size: 12px;
    color: var(--muted);
    letter-spacing: 1px;
  }

  @media (max-width: 600px) {
    .table-header, .row {
      grid-template-columns: 40px 1fr 60px 60px;
    }
    .cell.winrate, .table-header .h-winrate { display: none; }
    .cell.streak-col, .table-header .h-streak { display: none; }
  }
</style>
</head>
<body>

<div class="hero">
  <div class="hero-eyebrow">Serveur BALO</div>
  <div class="hero-title">Bataille<br>de Logos</div>
  <div class="hero-sub">Classement général · Mis à jour en temps réel</div>
</div>

<div class="stats-bar">
  <div class="stat-item">
    <div class="stat-value">{{ total_battles }}</div>
    <div class="stat-label">Batailles</div>
  </div>
  <div class="stat-item">
    <div class="stat-value">{{ total_players }}</div>
    <div class="stat-label">Participants</div>
  </div>
  <div class="stat-item">
    <div class="stat-value">{{ total_participations }}</div>
    <div class="stat-label">Soumissions</div>
  </div>
</div>

<div class="table-wrap">
  <div class="table-header">
    <span>#</span>
    <span>Joueur</span>
    <span style="text-align:center">Victoires</span>
    <span style="text-align:center">Participations</span>
    <span style="text-align:center h-winrate">Taux</span>
    <span style="text-align:center h-streak">Streak</span>
  </div>

  {% for p in players %}
  <div class="row">
    <div class="rank {{ 'gold' if loop.index == 1 else 'silver' if loop.index == 2 else 'bronze' if loop.index == 3 else '' }}">
      {{ '🥇' if loop.index == 1 else '🥈' if loop.index == 2 else '🥉' if loop.index == 3 else loop.index }}
    </div>
    <div class="username">
      {{ p.username }}
      {% if p.current_streak >= 3 %}
      <span class="streak-badge">🔥 ×{{ p.current_streak }}</span>
      {% endif %}
    </div>
    <div class="cell victories">{{ p.victories }}</div>
    <div class="cell">{{ p.participations }}</div>
    <div class="cell winrate">{{ p.win_rate }}%</div>
    <div class="cell streak-col">{{ p.best_streak }}</div>
  </div>
  {% endfor %}

  {% if not players %}
  <div style="text-align:center; padding: 48px; color: var(--muted);">
    Aucune donnée disponible pour l'instant.
  </div>
  {% endif %}
</div>

<div class="footer">
  Le Héraut · BALO · {{ year }}
</div>

</body>
</html>
"""


@app.route("/")
def leaderboard():
    players = db.get_all_stats()
    total_battles = db.get_total_battles()
    total_players = len(players)
    total_participations = sum(p["participations"] for p in players)
    from datetime import datetime
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
