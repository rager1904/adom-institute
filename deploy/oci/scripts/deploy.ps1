# ---------------------------------------------------------------------------
# ADOM Institute - deploy to the OCI app node (Windows PowerShell)
#
# Usage:
#   .\deploy.ps1 -PublicIp 140.238.x.x -Domain app.yourdomain.com -Email you@example.com
#
# Prereqs: Windows OpenSSH client (ssh/scp), tar (bsdtar, ships with Win10+).
# Run from the repo root.
# ---------------------------------------------------------------------------
param(
    [Parameter(Mandatory = $true)][string]$PublicIp,
    [Parameter(Mandatory = $true)][string]$Domain,
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$SshUser = "ubuntu",
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\id_ed25519"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Invoke-Remote([string]$Cmd) {
    ssh -i $SshKeyPath -o StrictHostKeyChecking=accept-new "$SshUser@$PublicIp" $Cmd
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed: $Cmd" }
}

# --- 1. generate secrets ---------------------------------------------------
$Py = Join-Path (Get-Location) "venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$SecretKey = & $Py -c "import secrets;print(secrets.token_urlsafe(50))"
$DbPass    = & $Py -c "import secrets;print(secrets.token_urlsafe(24))"

# --- 2. render production .env ---------------------------------------------
Write-Host "==> Building .env.production"
$template = Get-Content -Raw "deploy\oci\.env.production.example"
$envText = $template -replace '^SECRET_KEY=.*$', "SECRET_KEY=$SecretKey" `
                    -replace '^ALLOWED_HOSTS=.*$', "ALLOWED_HOSTS=$Domain" `
                    -replace '^CORS_ALLOWED_ORIGINS=.*$', "CORS_ALLOWED_ORIGINS=https://$Domain" `
                    -replace '^DB_PASSWORD=.*$', "DB_PASSWORD=$DbPass" `
                    -replace '^POSTGRES_PASSWORD=.*$', "POSTGRES_PASSWORD=$DbPass"
Set-Content -Path ".env.production" -Value $envText -Encoding utf8

# --- 3. sync project (tar pipe, excludes local junk) ------------------------
Write-Host "==> Syncing project to /opt/adom/app"
Invoke-Remote "mkdir -p /opt/adom/app /opt/adom/scripts"
$excludes = @(
    "--exclude", "venv", "--exclude", ".git", "--exclude", ".venv",
    "--exclude", "media", "--exclude", "staticfiles", "--exclude", "logs",
    "--exclude", "*.sqlite3", "--exclude", ".env", "--exclude", "*.pyc",
    "--exclude", "__pycache__", "--exclude", "deploy/oci/TERRAFORM/.terraform"
)
tar -czf - $excludes . |
    ssh -i $SshKeyPath "$SshUser@$PublicIp" "tar -xzf - -C /opt/adom/app"
if ($LASTEXITCODE -ne 0) { throw "File sync failed" }

# --- 4. upload scripts + env ------------------------------------------------
Write-Host "==> Uploading operator scripts and production env"
scp -i $SshKeyPath deploy\oci\scripts\*.sh "$SshUser@$PublicIp`:/opt/adom/scripts/"
scp -i $SshKeyPath .env.production "$SshUser@$PublicIp`:/opt/adom/app/.env"
$domainEsc = $Domain.Replace(".", "\.")
Invoke-Remote "chmod +x /opt/adom/scripts/*.sh && sed -i 's/DOMAIN_PLACEHOLDER/${domainEsc}/g' /opt/adom/app/deploy/oci/nginx/adom.conf"

# --- 5. build + migrate + start (nginx last, certificate first) ------------
Write-Host "==> Building images, running migrations, starting app services (first build takes a while)"
Invoke-Remote "cd /opt/adom/app && docker compose -f docker-compose.prod.yml up -d --build migrate"
Invoke-Remote "cd /opt/adom/app && docker compose -f docker-compose.prod.yml up -d --build db pgbouncer redis web ws worker beat"

# --- 6. TLS (standalone - port 80 must be free, nginx not started yet) ------
Write-Host "==> Issuing TLS certificate"
Invoke-Remote "cd /opt/adom/app && docker compose -f docker-compose.prod.yml run --rm -p 80:80 certbot certonly --standalone -d $Domain --email $Email --agree-tos --no-eff-email --non-interactive"

Write-Host "==> Starting nginx with the new certificate"
Invoke-Remote "cd /opt/adom/app && docker compose -f docker-compose.prod.yml up -d nginx"

Write-Host ""
Write-Host "Deploy complete. Next steps:"
Write-Host "  1. Create a superuser:"
Write-Host "     ssh -i $SshKeyPath ${SshUser}@${PublicIp} 'cd /opt/adom/app && docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser'"
Write-Host "  2. Point DNS A record $Domain -> $PublicIp"
Write-Host "  3. Optional: enable OCI Object Storage (see deploy/oci/README.md)"
Write-Host "  4. Verify:  https://$Domain/admin/"