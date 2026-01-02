# 🚀 Automated Deployment Guide

This guide explains how to use the `deploy.sh` script to pull latest code and restart the application on your VPS automatically.

---

## 🛠 Prerequisites

-   **Local Terminal**: Works on **macOS**, **Linux**, and **Windows** (Git Bash, WSL, or PowerShell 7).
-   **Server Credentials**:
    -   **Host**: `104.248.224.80`
    -   **User**: `root`
    -   **Password**: `R*ue7RKBGY+^48q$iAf3Fase$%1FAefzcx`

---

## ⚡ How to Deploy

Simply run the following command in your project root:

```bash
bash deploy.sh
```

### What the script does:

1.  **Safety Check**: Checks if the server has enough disk space.
2.  **Git Pull**: Pulls the latest changes from the `develop` branch.
3.  **App Restart**: Restarts the PM2 process `#25` (`slack-automation`).
4.  **Log Snapshot**: Shows you the last 15 lines of output and error logs.
5.  **Auto Exit**: Closes the connection and returns you to your local terminal.

---

## 🔒 Better Stability (SSH Keys)

To avoid typing the password every time and make deployment **much faster**:

### 1. Generate SSH Key (if you don't have one)

On your local machine, run:

```bash
ssh-keygen -t rsa -b 4096
```

_(Press Enter for all defaults)_

### 2. Copy Key to Server

```bash
ssh-copy-id root@104.248.224.80
```

_Enter the password one last time._

Now, `bash deploy.sh` will run instantly without asking for a password!

---

## 📊 Monitoring & Health

### View Live Logs

If you want to watch the logs in real-time without deploying:

```bash
ssh root@104.248.224.80 "pm2 logs 25"
```

### Check General Status

To see all running processes on the server:

```bash
ssh root@104.248.224.80 "pm2 status"
```

### Server Disk Warning

> [!WARNING] Your server is currently at **96% disk usage**. If it hits 100%, the application will crash. Please consider cleaning up old logs (`pm2 flush`) or temp files soon.
