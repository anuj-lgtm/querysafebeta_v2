# 🚀 QuerySafe Deployment Guide (GitHub Method)

Since you want to deploy via GitHub, follow these steps:

## Step 1: Push to GitHub

1.  Create a new repository on GitHub (e.g., `querysafe-beta`).
2.  Run these commands in your terminal:

```bash
git remote add origin https://github.com/DipanshuMetricVibes/querysafebeta.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Cloud Run

1.  Go to [Google Cloud Run Console](https://console.cloud.google.com/run).
2.  Click **"Create Service"**.
3.  Select **"Continuously deploy from a repository"**.
4.  Click **"Set up with Cloud Build"**.
    *   Connect your GitHub account.
    *   Select your repository (`querysafe-beta`).
    *   Click **Next**.
5.  **Build Configuration**:
    *   Select **Buildpacks** (Go, Node.js, Python, Java, .NET, Ruby, PHP).
    *   Click **Save**.
6.  **Configure Service**:
    *   Region: `asia-south1` (Mumbai).
    *   Authentication: **Allow unauthenticated invocations**.
7.  **Environment Variables** (CRITICAL):
    *   Click **"Container, Networking, Security"** -> **"Variables & Secrets"**.
    *   Add the following variables (copy from your `.env`):
        *   `SECRET_KEY`: (Your secret key)
        *   `DEBUG`: `False`
        *   `PROJECT_NAME`: `QuerySafe`
        *   `ALLOWED_HOSTS`: `.run.app`
        *   `EMAIL_HOST_USER`: `no-reply@metricvibes.com`
        *   `EMAIL_HOST_PASSWORD`: `MetricVibes@2025`
        *   (Add other keys like RAZORPAY if needed)
8.  Click **"Create"**.

## 🎉 Done!

Cloud Run will now:
1.  Pull code from GitHub.
2.  Build it using Buildpacks.
3.  Deploy it to a live URL.
4.  Auto-deploy whenever you push to GitHub!
