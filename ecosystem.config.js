// pm2 ecosystem — runs both the FastAPI server and Inngest dev server
//
// Usage (Mac Mini, one-time setup):
//   pm2 delete sundial          # remove old single-process setup if it exists
//   pm2 start ecosystem.config.js
//   pm2 save
//   pm2 startup                 # re-run the printed command if needed
//
// After a git pull:
//   pm2 restart all
//
// Logs:
//   pm2 logs sundial
//   pm2 logs sundial-inngest
//   pm2 logs              (all processes)

module.exports = {
  apps: [
    {
      name: 'sundial',
      script: 'uvicorn',
      args: 'server:app --port 3001',
      interpreter: 'none',
      cwd: __dirname,
      env: {
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
      },
    },
    {
      name: 'sundial-inngest',
      script: 'inngest',
      args: 'dev -u http://localhost:3001/api/inngest',
      interpreter: 'none',
      cwd: __dirname,
    },
  ],
}
