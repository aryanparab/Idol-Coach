#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — Build → ECR push → EC2 deploy for Idol Singing Coach backend
#
# USAGE:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# PREREQUISITES (fill in the variables below once):
#   • AWS CLI configured with ECR push permissions  (aws configure)
#   • Docker installed and running locally
#   • EC2 key pair .pem file accessible
#   • ECR repository already created
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── ✏️  Configuration — edit these before first run ──────────────────────────
AWS_ACCOUNT_ID="YOUR_AWS_ACCOUNT_ID"          # e.g. 123456789012
AWS_REGION="us-east-2"
ECR_REPO_NAME="idol-singing-coach"
IMAGE_TAG="latest"

EC2_HOST="YOUR_EC2_ELASTIC_IP"                # e.g. 3.141.59.26
EC2_USER="ubuntu"                             # default Ubuntu AMI user
EC2_KEY_PATH="~/.ssh/your-keypair.pem"        # path to your .pem file
EC2_APP_DIR="/home/ubuntu/idol-singing-coach" # where to keep the app on EC2

# S3 bucket (same as in your .env)
S3_BUCKET="idol-singing-coach"

# ── Derived values (no need to edit) ─────────────────────────────────────────
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_IMAGE="${ECR_REGISTRY}/${ECR_REPO_NAME}:${IMAGE_TAG}"

# ─────────────────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎤  Idol Singing Coach — Deploy Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Build Docker image ─────────────────────────────────────────────────────
echo ""
echo "▶  Step 1/5 — Building Docker image …"
docker build --platform linux/amd64 -t "${ECR_IMAGE}" .
echo "✅ Image built: ${ECR_IMAGE}"

# ── 2. Authenticate Docker with ECR ──────────────────────────────────────────
echo ""
echo "▶  Step 2/5 — Authenticating with ECR …"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
echo "✅ ECR login successful"

# ── 3. Push image to ECR ──────────────────────────────────────────────────────
echo ""
echo "▶  Step 3/5 — Pushing image to ECR …"
docker push "${ECR_IMAGE}"
echo "✅ Image pushed: ${ECR_IMAGE}"

# ── 4. Upload S3 migration (first deploy only — idempotent) ──────────────────
echo ""
echo "▶  Step 4/5 — Uploading songs to S3 (first-run / idempotent) …"
echo "   Run manually if not already done:"
echo "   PRODUCTION=true python scripts/upload_songs_to_s3.py"
echo "   (skipped in script to avoid accidental re-uploads)"

# ── 5. SSH to EC2 and redeploy ────────────────────────────────────────────────
echo ""
echo "▶  Step 5/5 — Deploying to EC2 (${EC2_HOST}) …"

# Load .env to pass secrets as docker run flags
# (assumes .env is in the repo root — never commit it to git)
if [ ! -f .env ]; then
  echo "❌ ERROR: .env file not found. Create one before deploying." >&2
  exit 1
fi

# Build env var flags from .env (skip blank lines and comments)
ENV_FLAGS=""
while IFS='=' read -r key value; do
  [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
  # Strip surrounding quotes from value if present
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  ENV_FLAGS+=" -e ${key}=${value}"
done < .env

ssh -i "${EC2_KEY_PATH}" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" bash -s <<REMOTE
set -euo pipefail

echo "  [EC2] Logging in to ECR …"
aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin ${ECR_REGISTRY}

echo "  [EC2] Pulling latest image …"
docker pull ${ECR_IMAGE}

echo "  [EC2] Stopping old container (if running) …"
docker stop idol-api 2>/dev/null || true
docker rm   idol-api 2>/dev/null || true

echo "  [EC2] Starting new container …"
docker run -d \
  --name idol-api \
  --restart always \
  -p 8000:8000 \
  ${ENV_FLAGS} \
  ${ECR_IMAGE}

echo "  [EC2] Container status:"
docker ps --filter name=idol-api --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
REMOTE

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅  Deploy complete!"
echo "   Backend: http://${EC2_HOST}:8000  (or https if Nginx + SSL is set up)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
