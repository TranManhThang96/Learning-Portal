# VPS deployment with PM2

This project builds VitePress in GitHub Actions, uploads the generated static files to the VPS, and reloads a PM2-managed Node static server.

## Required VPS setup

- Node.js `>=20.19.0`
- PM2 installed globally
- `rsync` installed
- A deployment directory writable by the SSH user, for example `/var/www/learning-portal`

Initial PM2 setup on the VPS after the first successful deploy:

```bash
cd /var/www/learning-portal
PORT=4173 pm2 startOrReload ecosystem.config.cjs --env production
pm2 save
pm2 startup
```

If Nginx is in front of PM2, proxy to `http://127.0.0.1:4173`.

## GitHub Secrets

Set these repository secrets:

| Secret | Required | Example |
| --- | --- | --- |
| `VPS_HOST` | Yes | `203.0.113.10` |
| `VPS_USER` | Yes | `deploy` |
| `VPS_SSH_KEY` | Yes | Private key for SSH login |
| `VPS_DEPLOY_PATH` | Yes | `/var/www/learning-portal` |
| `VPS_PORT` | No | `22` |
| `APP_PORT` | No | `4173` |

The workflow runs on pushes to `main` or `master`, and can also be started manually from GitHub Actions.
