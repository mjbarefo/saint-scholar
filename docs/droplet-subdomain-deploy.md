# Deploy Saint & Scholar To A DigitalOcean Droplet Subdomain

This guide deploys the current FastAPI app behind Nginx with TLS, served at `saint-scholar.jacob-barefoot.com`.

This setup is safe on droplets that already host other domains, as long as each Nginx server block has a unique `server_name` and no conflicting `default_server`.

## 1. DNS

In your DNS provider for `jacob-barefoot.com`, add:

- Type: `A`
- Host/Name: `saint-scholar`
- Value: your droplet public IPv4
- TTL: default

Wait for propagation before TLS setup.

## 2. Server packages (Ubuntu)

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx git
```

## 3. App user and checkout

```bash
sudo useradd --system --create-home --shell /bin/bash saintscholar || true
sudo mkdir -p /opt/saint-scholar
sudo chown -R saintscholar:saintscholar /opt/saint-scholar
sudo -u saintscholar git clone https://github.com/<you>/<repo>.git /opt/saint-scholar
cd /opt/saint-scholar
```

If the repo is already present, pull latest instead:

```bash
sudo -u saintscholar git -C /opt/saint-scholar pull --ff-only
```

## 4. Python environment and dependencies

```bash
cd /opt/saint-scholar
sudo -u saintscholar python3 -m venv .venv
sudo -u saintscholar /opt/saint-scholar/.venv/bin/pip install --upgrade pip
sudo -u saintscholar /opt/saint-scholar/.venv/bin/pip install -r requirements.txt
sudo -u saintscholar /opt/saint-scholar/.venv/bin/pip install -e .
```

## 5. Runtime env file

Create `/etc/saint-scholar.env`:

```bash
sudo tee /etc/saint-scholar.env >/dev/null <<'EOF'
ANTHROPIC_API_KEY=replace_me
ADMIN_API_KEY=replace_with_long_random_value
NCBI_EMAIL=you@example.com
EOF
sudo chmod 600 /etc/saint-scholar.env
```

## 6. Build vector store

Run once (or when corpus changes):

```bash
cd /opt/saint-scholar
sudo -u saintscholar /opt/saint-scholar/.venv/bin/python -m saint_scholar.ingest
```

## 7. Install systemd service

Copy the template in this repo:

```bash
sudo cp /opt/saint-scholar/ops/systemd/saint-scholar.service /etc/systemd/system/saint-scholar.service
sudo systemctl daemon-reload
sudo systemctl enable --now saint-scholar
sudo systemctl status saint-scholar --no-pager
```

## 8. Install Nginx site

The template is preconfigured for `saint-scholar.jacob-barefoot.com`:

```bash
sudo cp /opt/saint-scholar/ops/nginx/saint-scholar.conf /etc/nginx/sites-available/saint-scholar
sudo ln -sf /etc/nginx/sites-available/saint-scholar /etc/nginx/sites-enabled/saint-scholar
sudo nginx -t
sudo systemctl reload nginx
```

Optional sanity check on a multi-site droplet:

```bash
sudo nginx -T | grep -E "server_name|listen .*default_server"
```

## 9. Enable HTTPS

```bash
sudo certbot --nginx -d saint-scholar.jacob-barefoot.com
```

## 10. Verify

```bash
curl -sS https://saint-scholar.jacob-barefoot.com/health
curl -sS https://saint-scholar.jacob-barefoot.com/v1/figures
```

## Update workflow

```bash
cd /opt/saint-scholar
sudo -u saintscholar git pull --ff-only
sudo -u saintscholar /opt/saint-scholar/.venv/bin/pip install -r requirements.txt
sudo -u saintscholar /opt/saint-scholar/.venv/bin/pip install -e .
sudo systemctl restart saint-scholar
```

Or use the one-command deploy script:

```bash
cd /opt/saint-scholar
chmod +x ops/deploy.sh
sudo DOMAIN=saint-scholar.jacob-barefoot.com ./ops/deploy.sh
```

Optional rebuild of embeddings during deploy:

```bash
sudo DOMAIN=saint-scholar.jacob-barefoot.com RUN_INGEST=1 ./ops/deploy.sh
```

## Rollback

The deploy script saves snapshots at `/opt/saint-scholar/.deploy-backups/<timestamp>`.

List snapshots:

```bash
ls -1 /opt/saint-scholar/.deploy-backups
```

Rollback to latest snapshot:

```bash
cd /opt/saint-scholar
chmod +x ops/rollback.sh
sudo ./ops/rollback.sh
```

Rollback to a specific snapshot:

```bash
sudo ./ops/rollback.sh 20260305183000
```
