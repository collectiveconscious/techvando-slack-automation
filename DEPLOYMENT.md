# Deployment Guide

## Prerequisites
- A DigitalOcean Droplet (Ubuntu/Debian recommended)
- A domain name pointing to your Droplet's IP
- SSH access to the Droplet

## 1. Setup Environment
SSH into your droplet and navigate to your desired directory.

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and Nginx
sudo apt install python3-pip python3-venv nginx -y
```

## 2. Deploy Code
Copy the `automation` folder context to the server (e.g., using `scp` or git).

```bash
cd automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configure Environment Variables
Create the `.env` file and populate it with your real credentials.

```bash
cp .env.example .env
nano .env
```
*Ensure you have your `service_account.json` for Google Drive on the server and referenced correctly in `.env`.*

## 4. Run with Gunicorn (Test)
```bash
gunicorn --bind 0.0.0.0:8000 app:app
```
*Ctrl+C to stop after testing.*

## 5. Configure Nginx & HTTPS (Certbot)

### Install Certbot
```bash
sudo snap install core; sudo snap refresh core
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
```

### Configure Nginx
Create a config file: `/etc/nginx/sites-available/slack-automation`

```nginx
server {
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:
```bash
sudo ln -s /etc/nginx/sites-available/slack-automation /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

### Enable HTTPS
```bash
sudo certbot --nginx -d your-domain.com
```

## 6. Run Permanently (Systemd)
Create `/etc/systemd/system/slack-automation.service`:

```ini
[Unit]
Description=Gunicorn instance to serve Slack Automation
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/path/to/automation
Environment="PATH=/path/to/automation/venv/bin"
ExecStart=/path/to/automation/venv/bin/gunicorn --workers 3 --bind unix:app.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
```

Start the service:
```bash
sudo systemctl start slack-automation
sudo systemctl enable slack-automation
```
