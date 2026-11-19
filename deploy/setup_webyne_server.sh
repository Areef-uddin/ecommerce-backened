#!/usr/bin/env bash
# ==============================================================================
# Automated Production Deployment Script for Webyne VPS (157.15.203.209)
# Full-Stack: Django API (Gunicorn) + Flutter Web + React Vite Admin Panel + Nginx
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "🚀 Starting E-Commerce Deployment on Webyne VPS (157.15.203.209)"
echo "=========================================================="

# 1. Update system packages
echo "📦 Updating system packages..."
apt-get update -y
apt-get install -y \
    curl \
    git \
    ufw \
    nginx \
    python3 \
    python3-pip \
    python3-venv \
    libpq-dev \
    build-essential \
    unzip \
    tar

# 2. Install Node.js (v20 LTS) for React Admin Panel
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js LTS (v20)..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# 3. Clone or Update Repositories
mkdir -p /var/www/ecommerce
cd /var/www/ecommerce

# Backend
if [ -d "/var/www/ecommerce/backend/.git" ]; then
    echo "🔄 Pulling latest Backend changes..."
    cd /var/www/ecommerce/backend && git pull origin main
else
    echo "📥 Cloning Backend Repository..."
    rm -rf /var/www/ecommerce/backend
    git clone https://github.com/Areef-uddin/ecommerce-backened.git /var/www/ecommerce/backend
fi

# Admin Panel
if [ -d "/var/www/ecommerce/admin_panel/.git" ]; then
    echo "🔄 Pulling latest Admin Panel changes..."
    cd /var/www/ecommerce/admin_panel && git pull origin main
else
    echo "📥 Cloning Admin Panel Repository..."
    rm -rf /var/www/ecommerce/admin_panel
    git clone https://github.com/Areef-uddin/ecommerce-admin.git /var/www/ecommerce/admin_panel
fi

# Customer App
if [ -d "/var/www/ecommerce/customer_app/.git" ]; then
    echo "🔄 Pulling latest Customer App changes..."
    cd /var/www/ecommerce/customer_app && git pull origin main
else
    echo "📥 Cloning Customer App Repository..."
    rm -rf /var/www/ecommerce/customer_app
    git clone https://github.com/Areef-uddin/ecommerce-customerapp.git /var/www/ecommerce/customer_app
fi

# 4. Create directories & extract pre-built Flutter Web
echo "📁 Setting up media, static, and web directories..."
mkdir -p /var/www/ecommerce/backend/media/tryon_inputs
mkdir -p /var/www/ecommerce/backend/media/tryon_results
mkdir -p /var/www/ecommerce/backend/staticfiles
mkdir -p /var/www/ecommerce/customer_app/build/web

if [ -f "/var/www/ecommerce/backend/deploy/customer_web.tar.gz" ]; then
    echo "📦 Unpacking optimized Flutter Web release build..."
    tar -xzf /var/www/ecommerce/backend/deploy/customer_web.tar.gz -C /var/www/ecommerce/customer_app/build/web/
fi

# 5. Setup Backend Python Virtual Environment
echo "🐍 Configuring Python environment & dependencies..."
cd /var/www/ecommerce/backend

if [ ! -d "/var/www/ecommerce/backend/venv" ]; then
    python3 -m venv venv
fi

/var/www/ecommerce/backend/venv/bin/pip install --upgrade pip
/var/www/ecommerce/backend/venv/bin/pip install -r requirements.txt
/var/www/ecommerce/backend/venv/bin/pip install gunicorn pillow psycopg2-binary

# Create or Update .env with verified production credentials
echo "📝 Writing production .env for Backend..."
cat << 'EOF' > /var/www/ecommerce/backend/.env
DEBUG=False
SECRET_KEY=django-insecure-pro-ecom-webyne-vps-secure-key-2026!@#$%^
ALLOWED_HOSTS=157.15.203.209,localhost,127.0.0.1
DATABASE_URL=postgresql://neondb_owner:npg_THJfOw3sWN8v@ep-muddy-recipe-b4aa0hey-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require
CORS_ALLOW_ALL=True
FRONTEND_URL=http://157.15.203.209
TRYON_PROVIDER=auto
TRYON_IMAGE_MODEL=qwen/qwen-image-2.1-turbo
RAZORPAY_KEY_ID=rzp_test_Tt3TjWZ9FqBAW6
RAZORPAY_KEY_SECRET=3rEsnPCdmNjRsSGcclXyhWEe
EOF
chmod 600 /var/www/ecommerce/backend/.env

# 6. Run Migrations & Collect Static Files
echo "🗄️ Running database migrations & collecting static files..."
/var/www/ecommerce/backend/venv/bin/python manage.py migrate --noinput
/var/www/ecommerce/backend/venv/bin/python manage.py seed_data
/var/www/ecommerce/backend/venv/bin/python manage.py collectstatic --noinput

# 7. Build React Admin Panel
echo "⚛️ Building React Vite Admin Panel..."
cd /var/www/ecommerce/admin_panel
cat << 'EOF' > /var/www/ecommerce/admin_panel/.env
VITE_API_URL=http://157.15.203.209/api
EOF
npm install
npm run build

# 8. Setup Gunicorn Systemd Service
echo "⚙️ Setting up Gunicorn systemd service..."
cat << 'EOF' > /etc/systemd/system/ecommerce-backend.service
[Unit]
Description=Gunicorn instance for E-Commerce Django Backend
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/ecommerce/backend
EnvironmentFile=/var/www/ecommerce/backend/.env
ExecStart=/var/www/ecommerce/backend/venv/bin/gunicorn \
          --workers 3 \
          --bind 127.0.0.1:8000 \
          --timeout 120 \
          --access-logfile /var/log/gunicorn-access.log \
          --error-logfile /var/log/gunicorn-error.log \
          core.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ecommerce-backend
systemctl restart ecommerce-backend

# 9. Configure Nginx
echo "🌐 Configuring Nginx reverse proxy..."
cat << 'EOF' > /etc/nginx/sites-available/ecommerce
server {
    listen 80;
    listen [::]:80;
    server_name 157.15.203.209 _;

    client_max_body_size 50M;

    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/rss+xml application/atom+xml image/svg+xml font/woff2 font/woff;

    # Django API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 90s;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000/admin/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static Files
    location /static/ {
        alias /var/www/ecommerce/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # Uploads & Media
    location /media/ {
        alias /var/www/ecommerce/backend/media/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }

    # React Admin Panel
    location ^~ /admin-panel/ {
        alias /var/www/ecommerce/admin_panel/dist/;
        index index.html;
        try_files $uri $uri/ /admin-panel/index.html;
    }

    # Flutter Customer App
    location / {
        root /var/www/ecommerce/customer_app/build/web;
        index index.html;
        try_files $uri $uri/ /index.html;

        location = /index.html {
            add_header Cache-Control "no-store, no-cache, must-revalidate";
        }
    }
}
EOF

# Enable Nginx Site
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/ecommerce /etc/nginx/sites-enabled/ecommerce
nginx -t
systemctl restart nginx

# 10. Configure UFW Firewall (Security First)
echo "🔒 Securing firewall with UFW..."
ufw --force enable || true
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw status verbose

# 11. Final Health Check
echo "🩺 Verifying deployment health..."
sleep 2
if curl -s http://127.0.0.1:8000/api/products/items/ > /dev/null; then
    echo "✅ Django Backend API is responding successfully!"
else
    echo "⚠️ Backend verification returned non-200. Check logs: journalctl -u ecommerce-backend -n 20"
fi

echo "=========================================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "Customer Web App: http://157.15.203.209/"
echo "Admin Panel:      http://157.15.203.209/admin-panel/"
echo "API Endpoint:     http://157.15.203.209/api/"
echo "Django Admin:     http://157.15.203.209/admin/"
echo "=========================================================="
