# Deployment

## Live URL

**http://sundials-mac-mini:3001**

Accessible from any device on Ana's Tailscale network.

---

## Infrastructure

| Thing | Detail |
|-------|--------|
| Server | Mac Mini, always-on |
| Process manager | pm2 (`sundial` process) |
| Network | Tailscale — hostname `sundials-mac-mini` |
| Port | 3001 |
| Repo | git@github.com:anasofiaolano/sundial_meetings.git |

---

## Mac Mini setup (one-time, Python)

```bash
git clone git@github.com:anasofiaolano/sundial_meetings.git
cd sundial_meetings
pip3 install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...   # add to ~/.zshrc to persist
npm install -g pm2
pm2 start "uvicorn server:app --port 3001" --name sundial
pm2 save
pm2 startup   # run the command it prints to enable auto-start on boot
```

---

## Updating after a push

```bash
cd sundial_meetings && git pull && pm2 restart sundial
```

---

## Logs

```bash
pm2 logs sundial
```

---

## Migration note (Node → Python)

The original `server.js` (Node/Express) and `scripts/phase-2/apply-edits.js` are kept for reference but are no longer the active server. The Python equivalents are:

| Old (Node) | New (Python) |
|---|---|
| `server.js` | `server.py` |
| `scripts/phase-2/apply-edits.js` | `scripts/phase-2/apply_edits.py` |
| `node server.js` | `uvicorn server:app --port 3001` |
| `npm install` | `pip3 install -r requirements.txt` |
