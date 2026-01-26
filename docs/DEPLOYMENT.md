# Deployment Guide

This guide covers deploying TaskManager to production using the automated GitHub Actions workflow.

## Prerequisites

1. Production server with:
   - Docker and Docker Compose installed
   - SSH access configured
   - Project cloned to a deployment directory
   - `.env` file configured with production settings

2. GitHub repository secrets configured (see setup below)

## GitHub Secrets Setup

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `PRODUCTION_SSH_KEY` | Private SSH key for deployment | Contents of `~/.ssh/id_rsa` or dedicated deploy key |
| `PRODUCTION_HOST` | Production server hostname/IP | `todo.brooksmcmillin.com` or `192.168.1.100` |
| `PRODUCTION_USER` | SSH username | `brooks` |
| `PRODUCTION_DEPLOY_PATH` | Full path to project directory | `/home/brooks/build/taskmanager` |

### Generating SSH Deploy Key (Recommended)

On your local machine:

```bash
# Generate dedicated deploy key
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy

# Copy public key to production server
ssh-copy-id -i ~/.ssh/github_deploy.pub brooks@todo.brooksmcmillin.com

# Test connection
ssh -i ~/.ssh/github_deploy brooks@todo.brooksmcmillin.com

# Copy private key to GitHub Secrets
cat ~/.ssh/github_deploy
# Copy output and paste into PRODUCTION_SSH_KEY secret
```

## GitHub Environment Setup (Optional)

For additional protection, set up a production environment:

1. Go to **Settings → Environments → New environment**
2. Name: `production`
3. Configure protection rules:
   - ✅ Required reviewers (add yourself)
   - ✅ Wait timer: 5 minutes (optional)
4. Add environment-specific secrets (same as above)

This adds an extra approval step before deployment.

## Deployment Workflow

### Manual Deployment

1. Go to **Actions** tab in GitHub
2. Select **Deploy to Production** workflow
3. Click **Run workflow**
4. Fill in parameters:
   - Type `deploy` to confirm
   - Choose whether to skip backup (not recommended)
   - Choose whether to skip migrations
5. Click **Run workflow**

The workflow will:
1. ✅ Validate confirmation
2. 🔌 Connect to production server
3. 📦 Backup database
4. 📥 Pull latest code from `main`
5. 📦 Install dependencies
6. 🗄️ Run database migrations
7. 🔄 Rebuild and restart Docker services
8. 🏥 Run health checks
9. ✅ Report success or failure

### Tag-based Deployment (Future)

To enable automatic deployment on git tags:

```yaml
# Add to .github/workflows/deploy-production.yml
on:
  push:
    tags:
      - 'v*.*.*'
```

Then deploy by creating a tag:

```bash
git tag v1.2.3
git push origin v1.2.3
```

## Database Backups

### Create Manual Backup

On production server:

```bash
cd /home/brooks/build/taskmanager
make backup-db
```

Backups are stored in `backups/db_backup_YYYYMMDD_HHMMSS.sql`

### List Backups

```bash
make list-backups
```

### Restore from Backup

```bash
# Restore from latest backup
make restore-db

# Restore from specific backup
make restore-db file=backups/db_backup_20240126_120000.sql
```

## Rollback

If deployment fails or introduces issues:

### Quick Rollback (Previous Commit)

SSH to server and run:

```bash
cd /home/brooks/build/taskmanager

# Find previous commit
git log --oneline

# Reset to previous commit
git reset --hard <previous-commit-hash>

# Rebuild and restart
docker compose up -d --build

# Restore database if needed
make restore-db
```

### Database-Only Rollback

```bash
cd /home/brooks/build/taskmanager
make restore-db
```

## Health Checks

After deployment, verify services are running:

```bash
# Check container status
docker compose ps

# Check backend health
curl http://localhost:8000/health

# View logs
docker compose logs -f backend

# Check frontend
curl http://localhost:3000
```

## Troubleshooting

### Deployment Fails at "Pull latest code"

- Check SSH key permissions: `chmod 600 ~/.ssh/github_deploy`
- Verify server has internet access: `ping github.com`
- Ensure git is configured on server: `git config --global user.email`

### Deployment Fails at "Run database migrations"

- Check database is running: `docker compose ps postgres`
- Verify database credentials in `.env`
- Check migration files: `cd services/backend && uv run alembic current`

### Services Won't Start After Deployment

```bash
# Check Docker logs
docker compose logs backend frontend

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d

# Verify .env file is correct
cat .env
```

### Database Backup Fails

- Ensure `backups/` directory exists and is writable
- Check postgres container is running: `docker compose ps postgres`
- Verify database credentials

## Best Practices

1. **Always test on staging first** - Run through deployment on staging server before production
2. **Backup before deploying** - The workflow does this automatically, but verify backups exist
3. **Deploy during low-traffic periods** - Schedule deployments for off-peak hours
4. **Monitor after deployment** - Watch logs for 10-15 minutes after deploying
5. **Keep backups** - Retain at least 7 days of database backups
6. **Tag releases** - Tag commits in git for easy reference: `git tag v1.2.3`
7. **Review changes** - Always review git diff between current and new deployment

## Monitoring

Set up monitoring to catch issues:

```bash
# Watch logs in real-time
docker compose logs -f

# Check resource usage
docker stats

# Monitor error logs
docker compose logs backend | grep ERROR
```

## Future Improvements

- [ ] Blue-green deployment for zero downtime
- [ ] Automatic rollback on health check failure
- [ ] Slack/email notifications on deployment
- [ ] Database migration preview before applying
- [ ] Automated smoke tests after deployment
- [ ] Multiple environment support (staging, production)
