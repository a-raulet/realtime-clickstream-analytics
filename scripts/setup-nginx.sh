#!/bin/bash
#
# Setup Nginx reverse proxy with HTTPS for Clickstream Analytics
# Usage: ./setup-nginx.sh your-domain.com
#

set -e

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "Usage: ./setup-nginx.sh your-domain.com"
    exit 1
fi

echo "Setting up Nginx for $DOMAIN..."

# Install Nginx and Certbot
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

# Create Nginx config
cat > /etc/nginx/sites-available/clickstream << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_buffering off;
    }

    location /_stcore/stream {
        proxy_pass http://localhost:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/clickstream /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload
nginx -t
systemctl reload nginx

echo ""
echo "Nginx configured for $DOMAIN"
echo ""

# Setup HTTPS
read -p "Setup HTTPS with Let's Encrypt? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    certbot --nginx -d $DOMAIN
    echo ""
    echo "HTTPS configured!"
fi

# Remove direct port access from firewall
ufw delete allow 8501/tcp 2>/dev/null || true

echo ""
echo "Done! Your dashboard is now available at:"
echo "  http://$DOMAIN"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  https://$DOMAIN"
fi
