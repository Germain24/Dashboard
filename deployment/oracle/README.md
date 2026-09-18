# Mission Control sur Oracle Cloud Always Free

Ce profil cible une VM Oracle Ampere A1 ARM64. Il utilise les Dockerfiles déjà
présents dans le dépôt, Caddy pour HTTPS et quatre répertoires persistants :
`oracle-data`, `oracle-backups`, `oracle-caddy-data` et `oracle-caddy-config`.
Le volume `oracle-data` est également monté sur `/app/data` pour les anciens
chemins de cache et d'import du backend.

## Préparation Oracle

Créer une VM Ubuntu ARM64 dans la région principale du compte, avec au maximum
2 OCPU et 12 Go de mémoire au total. Autoriser TCP 80 et 443 dans la règle
réseau Oracle et dans `ufw`. Faire pointer le DNS `DOMAIN` vers l'IPv4 publique.

Installer Docker et Git, puis :

```bash
sudo mkdir -p /opt/mission-control
sudo chown "$USER" /opt/mission-control
git clone <URL_DU_DEPOT> /opt/mission-control
cd /opt/mission-control
cp .env.oracle.example .env.oracle
chmod 600 .env.oracle
```

Renseigner le domaine et les secrets dans `.env.oracle`, puis :

```bash
bash deployment/oracle/bootstrap.sh
```

Caddy demande automatiquement le certificat HTTPS dès que le DNS est correct.
Le premier build peut prendre plusieurs minutes sur ARM ; les images sont
ensuite réutilisées par Docker.

## Données et migration

Ne pas copier `.env` ni les bases personnelles dans Git. Transférer une archive
validée vers `oracle-data`, puis lancer les conteneurs ; le backend exécute les
migrations Alembic au démarrage. Les dossiers musique et imports non présents
sur la VM restent volontairement vides : ils ne doivent pas bloquer le module
finance.

Sauvegarde locale de la VM :

```bash
bash deployment/oracle/backup-data.sh
```

Pour l'automatiser avec systemd :

```bash
sudo install -m 644 deployment/oracle/mission-control-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mission-control-backup.timer
```

Copier périodiquement les archives vers un stockage externe. Le disque Oracle
n'est pas une sauvegarde contre la perte complète du compte.

## Exploitation

```bash
docker compose --env-file .env.oracle -f docker-compose.oracle.yml ps
docker compose --env-file .env.oracle -f docker-compose.oracle.yml logs -f backend
docker compose --env-file .env.oracle -f docker-compose.oracle.yml stop
docker compose --env-file .env.oracle -f docker-compose.oracle.yml start
```

Le backend reste volontairement à un seul worker : l'état de progression et les
quotas finance sont en mémoire et SQLite ne doit pas recevoir plusieurs workers.
Les recherches ETF et les vagues de remplacement sont déjà bornées par les
limites `ETF_RESEARCH_*`. Une seule optimisation doit être lancée à la fois.

## Vérification ARM avant migration

```bash
docker build --platform linux/arm64 -f backend/Dockerfile .
docker build --platform linux/arm64 -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://dashboard.example.com \
  --build-arg BACKEND_URL=http://backend:8000 .
```

Si une dépendance native ne fournit pas de wheel ARM, le build l'indiquera avant
le transfert des données. Dans ce cas, utiliser temporairement une VM x86 payante
ou conserver le moteur de calcul sur le PC local.
