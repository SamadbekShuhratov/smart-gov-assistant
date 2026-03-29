# Backend Deployment Guide (Option A: FastAPI on Railway)

This guide covers deploying the FastAPI backend to Railway and setting up Supabase for database/authentication.

## Architecture Overview

```
┌─────────────────┐
│  Vercel         │
│ (Frontend React)│────────┐
└─────────────────┘        │
                           │
                    _API_BASE
                           │
                           ▼
                    ┌──────────────┐
                    │ Railway      │
                    │ (FastAPI)    │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Supabase     │
                    │ (Postgres DB)│
                    │ (Auth)       │
                    └──────────────┘
```

## Part 1: Deploy Backend to Railway

### Prerequisites
- Railway account (free tier available at railway.app)
- Git repository pushed to GitHub
- Backend configured with Dockerfile ✅ (done)

### Steps

1. **Sign up / Login to Railway**
   - Visit https://railway.app
   - Click "Start Project"
   - Connect your GitHub account

2. **Create New Project**
   - Click "Create New" → "Empty Project"
   - Click "Add Service" → "GitHub Repo"
   - Select `SamadbekShuhratov/smart-gov-assistant` repository
   - Select root directory: `/` (or specify `backend/` if Railway auto-detects)

3. **Configure Environment Variables**
   - In Railway Dashboard → Project → Variables
   - Add variable `GEMINI_API_KEY` with your Google Generative AI key
   - **⚠️ SECURITY NOTE**: Your API key is currently in `backend/.env` in plaintext. Before deployment, move it to environment variables only.

4. **Deploy**
   - Railway automatically detects the Dockerfile
   - Deployment starts automatically after pushing
   - Monitor progress in Railway Dashboard
   - Once deployed, you'll receive a **Production URL** (e.g., `https://your-app.railway.app`)

### Verify Deployment

```bash
curl https://your-app.railway.app/docs
```

You should see the FastAPI Swagger UI.

---

## Part 2: Set Up Supabase (Optional - for Database/Auth)

### Prerequisites
- Supabase account (https://supabase.com)

### Steps

1. **Create Supabase Project**
   - Sign in to Supabase
   - Click "New Project"
   - Choose region closest to your users
   - Wait for initialization (2-3 minutes)

2. **Get Connection Details**
   - Go to Project Settings → Database
   - Copy:
     - `Host` (PostgreSQL connection host)
     - `Database` (default: `postgres`)
     - `Port` (default: `5432`)
     - `User` (default: `postgres`)
     - `Password` (save securely)

3. **Set Up Authentication (Optional)**
   - Go to Authentication → Providers
   - Enable desired auth methods (Email, Google, GitHub, etc.)

4. **Update Backend (If Using Supabase DB)**
   - Add to `backend/.env`:
     ```
     DATABASE_URL=postgresql://user:password@host:5432/database
     ```
   - Implement database models using Supabase SDK or SQLAlchemy

---

## Part 3: Connect Frontend to Backend

1. **Set Environment Variable in Vercel**
   - Go to Vercel Dashboard → frontend project → Settings → Environment Variables
   - Add: `VITE_API_BASE=https://your-railway-app.railway.app`
   - Click "Save & Deploy"

2. **Trigger Redeployment**
   - Go to Deployments → Redeploy production
   - Or push a commit to `main` branch

3. **Test Integration**
   - Visit frontend URL: https://frontend-halden.vercel.app
   - Try a service lookup (should call backend API)
   - Check browser DevTools Network tab to verify API calls to Railway

---

## Part 4: Security Checklist

Before going to production:

- [ ] Remove `GEMINI_API_KEY` from `backend/.env` file
- [ ] Use environment variables only for API keys
- [ ] Enable HTTPS (automatic on Railway & Vercel)
- [ ] Set up CORS properly in FastAPI (currently allows all origins)
- [ ] Add rate limiting to API endpoints
- [ ] Set up logging/monitoring on Railway Dashboard
- [ ] Use Supabase Row Level Security (RLS) for database access
- [ ] Enable Supabase Auth JWT verification in FastAPI

---

## Troubleshooting

### Backend Deployment Failed
```
Solution: Check Railway logs (Dashboard → Deployments → View Logs)
Common issues:
  - Missing GEMINI_API_KEY environment variable
  - Docker build error (check Dockerfile syntax)
  - Port 8000 already in use
```

### 401/403 on API Calls
```
Solution: Verify VITE_API_BASE is set correctly in Vercel
- Check Vercel Environment Variables
- Verify Railway deployment URL is correct
- Test with curl: curl https://your-railway-app/docs
```

### CORS Errors
```
Solution: Backend currently allows all origins. To restrict:
Edit backend/app/main.py line ~70:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend-halden.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Monitoring & Maintenance

- **Railway Dashboard**: Real-time logs, metrics, deployments
- **Vercel Dashboard**: Frontend deployment history, analytics
- **Supabase Dashboard**: Database browser, Auth logs, API activity

---

## Next Steps

1. ✅ Backend configured with Docker
2. → Deploy backend to Railway (this document Step 1)
3. → Set up Supabase (optional, Step 2)
4. → Connect frontend to backend (Step 3)
5. → Run end-to-end tests
6. → Monitor and optimize performance

---

## Quick Deployment Command

If re-deploying after code changes:

```bash
cd /workspaces/smart-gov-assistant
git add -A
git commit -m "backend: [description of changes]"
git push origin main
```

Railway automatically redeploys on git push to main branch.
