# Idol Singing Coach — Deployment Guide

> **Architecture**: FastAPI backend on EC2 (t2.micro) behind Nginx · Next.js 15 frontend on Vercel · MongoDB Atlas · AWS S3 (`idol-singing-coach`, us-east-2)

---

## 1. One-time AWS setup

### 1a. Create ECR repository
```bash
aws ecr create-repository \
  --repository-name idol-singing-coach \
  --region us-east-2
```

### 1b. EC2 instance prerequisites (run once after SSH-ing in)
```bash
# Install Docker
sudo apt-get update && sudo apt-get install -y docker.io awscli
sudo usermod -aG docker ubuntu
# Log out and back in for group change to take effect

# Install Nginx (for reverse proxy + SSL)
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Point your domain's A record (or just use the Elastic IP directly for HTTP)
```

### 1c. Nginx + SSL (skip if using plain HTTP with Elastic IP)
```bash
# Copy nginx.conf to the server
scp -i ~/.ssh/your-keypair.pem nginx.conf ubuntu@YOUR_EC2_IP:/etc/nginx/nginx.conf

# Replace YOUR_DOMAIN in the conf with your actual domain, then:
sudo certbot --nginx -d YOUR_DOMAIN

# Reload Nginx
sudo systemctl reload nginx
sudo systemctl enable nginx
```

---

## 2. Backend deploy (ECR → EC2)

### 2a. Fill in deploy.sh variables
Edit `deploy.sh` and set:
| Variable | Example |
|---|---|
| `AWS_ACCOUNT_ID` | `123456789012` |
| `AWS_REGION` | `us-east-2` |
| `ECR_REPO_NAME` | `idol-singing-coach` |
| `EC2_HOST` | `3.141.59.26` (Elastic IP) |
| `EC2_KEY_PATH` | `~/.ssh/idol-coach.pem` |

### 2b. Create `.env` in the repo root (never commit this)
```
PRODUCTION=true
MONGODB_URI=mongodb+srv://parabaryan:...@cluster1.twf29ul.mongodb.net/
MONGODB_DB=idol-coach
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-2
S3_BUCKET=idol-singing-coach
GROQ_API_KEY=gsk_...
FRONTEND_URL=https://your-app.vercel.app
BACKEND_URL=https://YOUR_DOMAIN  # or http://YOUR_EC2_IP:8000 for plain HTTP
```

### 2c. Upload songs to S3 (first deploy only)
```bash
# Run from repo root with your .env loaded
set -a && source .env && set +a
python scripts/upload_songs_to_s3.py
```

### 2d. Run the deploy script
```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Build the Docker image for `linux/amd64`
2. Push it to ECR
3. SSH to EC2, pull the image, and restart the `idol-api` container with `--restart always`

### 2e. Verify
```bash
curl http://YOUR_EC2_IP:8000/health        # or https://YOUR_DOMAIN/health
# Should return {"status": "ok"} (add a /health route to main.py if missing)
```

---

## 3. Frontend deploy (Vercel)

### 3a. Push frontend to its own repo (or use a monorepo with `Root Directory` set)
Vercel can deploy from a subdirectory — in the Vercel dashboard set **Root Directory** to `idol-singing-coach-frontend`.

### 3b. Set environment variables in Vercel dashboard
Go to **Project → Settings → Environment Variables** and add:

| Key | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://YOUR_DOMAIN` or `http://YOUR_EC2_IP:8000` | Public — used by browser |
| `NEXTAUTH_URL` | `https://your-app.vercel.app` | Your Vercel deployment URL |
| `NEXTAUTH_SECRET` | `83742i749812oq7819o2190129210812` | Generate new: `openssl rand -base64 32` |
| `GOOGLE_CLIENT_ID` | `36937494431-qtk00agrtvmhdu0j...` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | `GOCSPX-dzDOc9K9y...` | From Google Cloud Console |
| `MONGODB_URI` | `mongodb+srv://parabaryan:...` | Same Atlas cluster |
| `MONGODB_DB` | `idol-coach` | |

### 3c. Update Google OAuth redirect URI
In **Google Cloud Console → APIs → Credentials → OAuth 2.0 Client**:
- Add `https://your-app.vercel.app/api/auth/callback/google` to **Authorized redirect URIs**

### 3d. Deploy
```bash
# From inside idol-singing-coach-frontend/
npx vercel --prod
# Or push to main branch if CI is set up
```

---

## 4. Updating the backend (subsequent deploys)
```bash
./deploy.sh   # builds → pushes → SSH restarts container
```

## 5. Logs
```bash
# Live container logs
ssh -i ~/.ssh/your-keypair.pem ubuntu@YOUR_EC2_IP "docker logs -f idol-api"

# Nginx logs
ssh -i ~/.ssh/your-keypair.pem ubuntu@YOUR_EC2_IP "sudo tail -f /var/log/nginx/error.log"
```
