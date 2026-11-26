#!/bin/bash
# rental-agent-prototype host bootstrap (Amazon Linux 2023). No secrets in this script.
# Before use: replace __ACCOUNT__ with your AWS account ID (sed -i "s/__ACCOUNT__/<account-id>/g" deploy/ec2-userdata.sh).
# Pin the image tag in IMAGE below; to update later, edit /etc/rental-agent.conf on the host and run: systemctl restart rental-agent
set -euxo pipefail
dnf install -y docker
systemctl enable --now docker
mkdir -p /srv/rental-data && chown 1000:1000 /srv/rental-data

cat > /etc/rental-agent.conf <<'CONF'
REGION=us-east-1
REGISTRY=__ACCOUNT__.dkr.ecr.us-east-1.amazonaws.com
IMAGE=__ACCOUNT__.dkr.ecr.us-east-1.amazonaws.com/rental_agent_prototype:1266e29
CONF

cat > /usr/local/bin/rental-agent-run <<'RUN'
#!/bin/bash
# Pull the pinned image, read the staff password into tmpfs, run the app in the foreground.
set -euo pipefail
source /etc/rental-agent.conf
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker pull "$IMAGE"
umask 077
printf 'STAFF_PASSWORD=%s\n' "$(aws secretsmanager get-secret-value --region "$REGION" --secret-id rental-agent/staff-password --query SecretString --output text)" > /run/rental-agent.env
docker rm -f rental-agent >/dev/null 2>&1 || true
exec docker run --name rental-agent --rm -p 80:8000 -v /srv/rental-data:/data \
  --env-file /run/rental-agent.env \
  -e AWS_REGION="$REGION" \
  -e BEDROCK_MODEL_CHAT=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  -e BEDROCK_MODEL_BACKOFFICE=us.anthropic.claude-sonnet-4-6 \
  -e PROJECT_NAME=rental-demo -e DATABASE_PATH=/data/app.db -e SESSION_COOKIE_SECURE=1 \
  --log-opt max-size=10m --log-opt max-file=3 \
  "$IMAGE"
RUN
chmod 755 /usr/local/bin/rental-agent-run

cat > /etc/systemd/system/rental-agent.service <<'UNIT'
[Unit]
Description=rental-agent-prototype container
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/rental-agent-run
ExecStop=/usr/bin/docker stop rental-agent
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now rental-agent.service
