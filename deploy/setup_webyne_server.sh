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

# Remove MySQL server completely
echo "🧹 Removing MySQL server completely..."
systemctl stop mysql 2>/dev/null || true
systemctl disable mysql 2>/dev/null || true
apt-get remove --purge -y mysql-server mysql-client mysql-common 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true

apt-get update -y
apt-get install -y \
    curl \
    git \
    ufw \
    nginx \
    python3 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    libpq-dev \
    pkg-config \
    php-fpm \
    php-pgsql \
    build-essential \
    unzip \
    tar

# 1.1 Setup and Configure Local PostgreSQL Server
echo "🐘 Setting up and securing local PostgreSQL Server on VPS..."
systemctl enable postgresql
systemctl start postgresql

# Avoid permission denied when running psql as postgres from /root
cd /tmp

sudo -u postgres psql -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ecommerce_user') THEN CREATE ROLE ecommerce_user WITH LOGIN PASSWORD 'StyleHub_Postgres_2026!#$'; END IF; END \$\$;"
sudo -u postgres psql -c "ALTER ROLE ecommerce_user WITH LOGIN PASSWORD 'StyleHub_Postgres_2026!#$';"

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='ecommerce_db'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE ecommerce_db OWNER ecommerce_user;"
fi

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_user;"
sudo -u postgres psql -d ecommerce_db -c "GRANT ALL ON SCHEMA public TO ecommerce_user;"
sudo -u postgres psql -d ecommerce_db -c "ALTER SCHEMA public OWNER TO ecommerce_user;"

cd /var/www/ecommerce

# 1.2 Setup Official pgAdmin 4 Web GUI
echo "🐘 Setting up official pgAdmin 4 Web GUI..."
curl -fsS https://www.pgadmin.org/static/packages_pgadmin_org.pub | gpg --dearmor --yes -o /usr/share/keyrings/packages-pgadmin-org.gpg 2>/dev/null || true
echo "deb [signed-by=/usr/share/keyrings/packages-pgadmin-org.gpg] https://ftp.postgresql.org/pub/pgadmin/pgadmin4/apt/jammy pgadmin4 main" > /etc/apt/sources.list.d/pgadmin4.list
apt-get update -y
apt-get install -y pgadmin4-web

mkdir -p /var/lib/pgadmin /var/log/pgadmin /etc/pgadmin
cat << 'EOF' > /usr/pgadmin4/web/config_local.py
import os
DATA_DIR = '/var/lib/pgadmin'
LOG_FILE = '/var/log/pgadmin/pgadmin4.log'
SQLITE_PATH = '/var/lib/pgadmin/pgadmin4.db'
SESSION_DB_PATH = '/var/lib/pgadmin/sessions'
STORAGE_DIR = '/var/lib/pgadmin/storage'
SERVER_MODE = True
DEFAULT_SERVER = '127.0.0.1'
DEFAULT_SERVER_PORT = 5050
MASTER_PASSWORD_REQUIRED = False
EOF

cat << 'EOF' > /etc/pgadmin/servers.json
{
  "Servers": {
    "1": {
      "Name": "StyleHub Local PostgreSQL",
      "Group": "Servers",
      "Host": "127.0.0.1",
      "Port": 5432,
      "MaintenanceDB": "ecommerce_db",
      "Username": "ecommerce_user",
      "SSLMode": "prefer"
    }
  }
}
EOF

# Initialize pgAdmin 4 admin user non-interactively
export PGADMIN_SETUP_EMAIL="admin@stylehub.com"
export PGADMIN_SETUP_PASSWORD="StyleHubPgAdmin2026!#$"
/usr/pgadmin4/venv/bin/python3 /usr/pgadmin4/web/setup.py --load-servers /etc/pgadmin/servers.json 2>/dev/null || true

chown -R www-data:www-data /var/lib/pgadmin /var/log/pgadmin 2>/dev/null || true

cat << 'EOF' > /etc/systemd/system/pgadmin4.service
[Unit]
Description=pgAdmin 4 Web GUI Service
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/usr/pgadmin4/web
Environment="PGADMIN_DEFAULT_EMAIL=admin@stylehub.com"
Environment="PGADMIN_DEFAULT_PASSWORD=StyleHubPgAdmin2026!#$"
ExecStart=/usr/pgadmin4/venv/bin/gunicorn --bind 0.0.0.0:5050 --workers 1 --threads 4 pgAdmin4:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pgadmin4
systemctl restart pgadmin4

# 1.3 Setup Adminer (Universal Web Database Manager - supports PostgreSQL with 1-click Auto-Login)
echo "🐘 Setting up Adminer (Web Database GUI for PostgreSQL)..."
mkdir -p /var/www/adminer
curl -sSL https://github.com/vrana/adminer/releases/download/v4.8.1/adminer-4.8.1.php -o /var/www/adminer/adminer-core.php

cat << 'EOF' > /var/www/adminer/index.php
<?php
function adminer_object() {
    class AdminerSoftware extends Adminer {
        function name() {
            return 'StyleHub PostgreSQL Console';
        }
        function credentials() {
            return array('localhost', 'ecommerce_user', 'StyleHub_Postgres_2026!#$');
        }
        function database() {
            return 'ecommerce_db';
        }
        function login($login, $password) {
            return true;
        }
    }
    return new AdminerSoftware;
}
include './adminer-core.php';
EOF
chmod 644 /var/www/adminer/index.php /var/www/adminer/adminer-core.php

PHP_SOCK=$(find /run/php/ -name "php*-fpm.sock" 2>/dev/null | head -n 1 || echo "/run/php/php8.1-fpm.sock")
PHP_SERVICE=$(systemctl list-unit-files | grep -oE "php[0-9.]+-fpm" | head -n 1 || echo "php8.1-fpm")
systemctl enable "$PHP_SERVICE" || true
systemctl restart "$PHP_SERVICE" || true

# Ensure localhost is resolvable in /etc/hosts
grep -q "127.0.0.1.*localhost" /etc/hosts || echo "127.0.0.1 localhost" >> /etc/hosts

# 1.4 Setup FileBrowser (Web File Manager to view/upload/edit all server files)
echo "📂 Setting up FileBrowser (Web File Manager)..."
systemctl stop filebrowser 2>/dev/null || true
if ! command -v filebrowser &> /dev/null; then
    curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash
fi

mkdir -p /etc/filebrowser
if [ ! -f "/etc/filebrowser/filebrowser.db" ]; then
    filebrowser config init -d /etc/filebrowser/filebrowser.db
fi
filebrowser config set -d /etc/filebrowser/filebrowser.db --root /var/www/ecommerce --port 8085 --address 0.0.0.0
filebrowser users update admin -p "StyleHubFiles2026!" -d /etc/filebrowser/filebrowser.db 2>/dev/null || \
filebrowser users add admin "StyleHubFiles2026!" --perm.admin -d /etc/filebrowser/filebrowser.db 2>/dev/null || true

cat << 'EOF' > /etc/systemd/system/filebrowser.service
[Unit]
Description=FileBrowser Web File Manager
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/filebrowser -d /etc/filebrowser/filebrowser.db
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable filebrowser
systemctl restart filebrowser

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

# Create or Update .env with verified production credentials (Local PostgreSQL)
echo "📝 Writing production .env for Backend (Local PostgreSQL)..."
cat << 'EOF' > /var/www/ecommerce/backend/.env
DEBUG=False
SECRET_KEY=django-insecure-pro-ecom-webyne-vps-secure-key-2026!@#$%^
ALLOWED_HOSTS=157.15.203.209,localhost,127.0.0.1
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD=StyleHub_Postgres_2026!#$
DB_HOST=127.0.0.1
DB_PORT=5432
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

    # Visual Database GUI (Adminer - Universal Web GUI)
    location = /db-admin {
        return 301 /db-admin/;
    }

    location ^~ /db-admin/ {
        alias /var/www/adminer/;
        index index.php;
        try_files $uri $uri/ /db-admin/index.php$is_args$args;

        location ~ \.php$ {
            include fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $request_filename;
            fastcgi_pass unix:__PHP_SOCK__;
        }
    }

    # pgAdmin 4 Web GUI
    location /pgadmin4/ {
        proxy_pass http://127.0.0.1:5050/;
        proxy_set_header X-Script-Name /pgadmin4;
        proxy_set_header Host $host;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_redirect off;
    }

    # FileBrowser Web File Manager
    location /files/ {
        proxy_pass http://127.0.0.1:8085/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # React Admin Panel
    location = /admin-panel {
        return 301 /admin-panel/;
    }

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

# Substitute detected PHP-FPM socket into Nginx config
PHP_SOCK=$(find /run/php/ -name "php*-fpm.sock" 2>/dev/null | head -n 1 || echo "/run/php/php8.1-fpm.sock")
sed -i "s|__PHP_SOCK__|$PHP_SOCK|g" /etc/nginx/sites-available/ecommerce

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
ufw allow 5050/tcp
ufw allow 8085/tcp
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
echo "Customer Web App:       http://157.15.203.209/"
echo "Admin Panel:            http://157.15.203.209/admin-panel/"
echo "API Endpoint:           http://157.15.203.209/api/"
echo "Django Admin:           http://157.15.203.209/admin/"
echo "pgAdmin 4 Web GUI:      http://157.15.203.209:5050 (or http://157.15.203.209/pgadmin4/)"
echo "FileBrowser Manager:    http://157.15.203.209:8085"
echo "Adminer Web Console:    http://157.15.203.209/db-admin/"
echo "=========================================================="
