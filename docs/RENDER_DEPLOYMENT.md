# Deploying PatchHive to Render

Complete guide to deploying PatchHive on Render's free tier.

## Quick Deploy (Recommended)

### Option 1: Deploy with Blueprint (Easiest)

1. **Fork or push this repository to GitHub**

2. **Go to Render Dashboard**
   - Visit [render.com](https://render.com)
   - Sign up or log in with GitHub

3. **Create New Blueprint**
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect `render.yaml`
   - Click "Apply"

4. **Set Environment Variables** (if needed)
   - Backend service: SECRET_KEY is auto-generated
   - Frontend service: VITE_API_URL is auto-configured
   - Database: Automatically provisioned

5. **Wait for Deployment**
   - Initial deploy takes 5-10 minutes
   - Database → Backend → Frontend

6. **Access Your App**
   - Frontend: `https://patchhive-frontend.onrender.com`
   - Backend API: `https://patchhive-api.onrender.com`
   - API Docs: `https://patchhive-api.onrender.com/docs`

### Option 2: Manual Deployment

If you prefer manual setup or need custom configuration:

---

## Manual Deployment Steps

### 1. Deploy PostgreSQL Database

1. In Render Dashboard, click "New +" → "PostgreSQL"
2. Configure:
   - **Name**: `patchhive-db`
   - **Database**: `patchhive`
   - **User**: `patchhive`
   - **Region**: Oregon (or closest to you)
   - **Plan**: Free
3. Click "Create Database"
4. **Save the Internal Database URL** (you'll need it for the backend)

### 2. Deploy Backend API

1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Name**: `patchhive-api`
   - **Region**: Oregon (same as database)
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free

4. **Add Environment Variables**:
   ```
   DATABASE_URL = <your-postgres-internal-url>
   CORS_ORIGINS = https://patchhive-frontend.onrender.com
   SECRET_KEY = <generate-random-string>
   APP_NAME = PatchHive
   APP_VERSION = 1.0.0
   ABX_CORE_VERSION = 1.2
   ENFORCE_SEED_TRACEABILITY = true
   ```

5. Click "Create Web Service"

### 3. Deploy Frontend

1. Click "New +" → "Static Site"
2. Connect your GitHub repository
3. Configure:
   - **Name**: `patchhive-frontend`
   - **Region**: Oregon
   - **Branch**: `main`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
   - **Plan**: Free

4. **Add Environment Variable**:
   ```
   VITE_API_URL = https://patchhive-api.onrender.com
   ```

5. **Add Rewrite Rule** (for client-side routing):
   - Source: `/*`
   - Destination: `/index.html`
   - Action: Rewrite

6. Click "Create Static Site"

---

## Environment Variables Reference

### Backend API Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | - | PostgreSQL connection string |
| `CORS_ORIGINS` | ✅ Yes | `*` | Allowed CORS origins (comma-separated) |
| `SECRET_KEY` | ✅ Yes | - | JWT secret key (generate random 32+ chars) |
| `APP_NAME` | No | PatchHive | Application name |
| `APP_VERSION` | No | 1.0.0 | Application version |
| `ABX_CORE_VERSION` | No | 1.2 | ABX-Core compliance version |
| `ENFORCE_SEED_TRACEABILITY` | No | true | Enforce SEED provenance |

### Frontend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | ✅ Yes | - | Backend API URL |

---

## Post-Deployment Configuration

### 1. Update CORS Origins

After frontend deployment, update backend CORS:

1. Go to backend service → Environment
2. Update `CORS_ORIGINS` to your actual frontend URL:
   ```
   https://patchhive-frontend.onrender.com,https://www.yourapp.com
   ```
3. Save and redeploy

### 2. Set Up Custom Domain (Optional)

**For Frontend**:
1. Go to frontend service → Settings → Custom Domains
2. Add your domain (e.g., `app.patchhive.com`)
3. Update DNS with provided CNAME record

**For Backend**:
1. Go to backend service → Settings → Custom Domains
2. Add subdomain (e.g., `api.patchhive.com`)
3. Update DNS with provided CNAME record
4. Update frontend `VITE_API_URL` to new API domain

### 3. Initialize Database

The backend Docker image runs **`alembic upgrade head`** via `docker-entrypoint.sh` before Uvicorn starts only when `RUN_MIGRATIONS` is `true` or `1` (default off). `render.yaml` sets `RUN_MIGRATIONS=true` for this self-contained Render stack. Do **not** rely on `create_all()` / `init_db()` for deploy.

**Manual migrations** (shell):
```bash
cd /app && python -m alembic upgrade head
python -m alembic current
```

**Readiness probe:** `GET /health/ready` (DB connectivity). Liveness-only: `GET /health`.

---

## Monitoring & Maintenance

### View Logs

**Backend Logs**:
- Go to backend service → Logs
- Monitor API requests and errors

**Frontend Build Logs**:
- Go to frontend service → Logs → Builds
- Check for build errors

### Health Checks

- Backend health: `https://patchhive-api.onrender.com/health`
- Expected response:
  ```json
  {
    "status": "healthy",
    "app": "PatchHive",
    "version": "1.0.0",
    "abx_core_version": "1.2"
  }
  ```

### Free Tier Limitations

⚠️ **Important**: Render free tier services:
- Spin down after 15 minutes of inactivity
- Take 30-50 seconds to wake up on first request
- Free PostgreSQL expires after 90 days (backup data!)
- 750 hours/month free (good for 1 service running 24/7)

**Solutions**:
- Use a health check service (e.g., UptimeRobot) to ping every 14 minutes
- Upgrade to paid tier ($7/month) for always-on services
- Export database backups regularly

---

## Troubleshooting

### Build Failures

**Backend**:
- Check `requirements.txt` is present
- Ensure Python version is 3.11+
- Check build logs for missing dependencies

**Frontend**:
- Ensure `package.json` and `package-lock.json` are committed
- Check Node version (should be 18+)
- Verify build command: `npm run build` works locally

### Runtime Errors

**Database Connection Issues**:
- Verify `DATABASE_URL` is set correctly
- Check database is in same region as backend
- Ensure database is active (not suspended)

**CORS Errors**:
- Update `CORS_ORIGINS` to include frontend URL
- Don't include trailing slash in URLs
- Redeploy backend after changing CORS settings

**API Not Responding**:
- Check backend logs for errors
- Verify health check endpoint works
- Service may be spinning up (wait 30-50 seconds)

### Frontend Can't Connect to Backend

1. Check `VITE_API_URL` is set correctly
2. Verify backend service is running
3. Test API directly: `curl https://patchhive-api.onrender.com/health`
4. Check browser console for CORS errors

---

## Upgrading from Free Tier

When ready to upgrade:

1. **Backend & Database**: $7/month each
   - Always-on (no spin down)
   - Better performance
   - Persistent database

2. **Frontend**: Free tier is usually sufficient
   - Static sites don't spin down

3. **Total Cost**: ~$14/month for production-ready setup

---

## CI/CD Integration

Render automatically redeploys on git push to `main` branch.

**To enable auto-deploy**:
1. Each service → Settings → Build & Deploy
2. Enable "Auto-Deploy"
3. Select branch (`main`)
4. Push to trigger deployment

**Deploy hooks** (for manual triggers):
- Backend: `curl -X POST https://api.render.com/deploy/srv-xxx`
- Frontend: `curl -X POST https://api.render.com/deploy/srv-yyy`

---

## Alternative: Deploy All at Once

### Using Render Blueprint (render.yaml)

The included `render.yaml` deploys everything automatically:

```bash
git push origin main
```

Then in Render:
1. New → Blueprint
2. Select repo
3. Apply

All services deploy in correct order with dependencies.

---

## Security Best Practices

1. **Generate Strong SECRET_KEY**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Use Environment Variables** - Never commit secrets

3. **Enable HTTPS** - Render provides free SSL certificates

4. **Restrict CORS** - Only allow your frontend domain

5. **Database Backups** - Export weekly:
   - Database → Settings → Backups
   - Or use pg_dump via CLI

6. **Monitor Logs** - Check for suspicious activity

---

## Support & Resources

- **Render Docs**: https://render.com/docs
- **Render Community**: https://community.render.com
- **PatchHive Issues**: https://github.com/scrimshawlife-ctrl/Patch-Hive/issues

---

## Quick Reference: Service URLs

After deployment, your services will be available at:

- **Frontend**: `https://patchhive-frontend.onrender.com`
- **Backend API**: `https://patchhive-api.onrender.com`
- **API Docs**: `https://patchhive-api.onrender.com/docs`
- **Health Check**: `https://patchhive-api.onrender.com/health`

**Note**: Replace `patchhive-frontend` and `patchhive-api` with your actual service names if different.

---

🎉 **Congratulations!** Your PatchHive instance is now live on Render!
