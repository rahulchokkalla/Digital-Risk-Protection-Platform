# Deploying ShieldWatch to Render

Your project is completely configured and ready to deploy on **Render**.

---

## Method 1: Deploy via GitHub (Recommended - 2 Minutes)

### Step 1: Push your code to GitHub
Run the following in your terminal (replace `<your-username>` and `<your-repo>`):
```bash
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

### Step 2: Create a Web Service on Render
1. Go to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** > **Web Service**.
3. Connect your GitHub repository.
4. Fill in the deployment settings:
   - **Name**: `shieldwatch` (or any name you choose)
   - **Language / Runtime**: `Python 3`
   - **Region**: Choose closest to you (e.g., Singapore, Frankfurt, Oregon)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirement.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`

### Step 3: Deploy!
Click **Deploy Web Service**.
Once the build completes (approx. 1-2 minutes), Render will give you your live URL:
`https://shieldwatch-xxxx.onrender.com`

When you open this URL in your browser, your **complete ShieldWatch Dashboard UI** will load immediately.

---

## Method 2: 1-Click Blueprint (`render.yaml`)

Because `render.yaml` is included in your repository, you can also:
1. In Render Dashboard, click **New +** > **Blueprint**.
2. Select your repository.
3. Render reads `render.yaml` and auto-configures everything!

---

## Database Configuration on Render

### Default (Server-side File Storage - Zero Configuration)
By default, the server uses a persistent file database (`shieldwatch.db`). No configuration or external database is required.

### Optional: Using External MySQL on Render
If you want to connect to a cloud MySQL database (e.g. from Aiven, TiDB Serverless, Clever Cloud):
1. In your Render Web Service dashboard, go to the **Environment** tab.
2. Add the following environment variables:
   - `DB_TYPE` = `mysql`
   - `DB_HOST` = `<your-cloud-mysql-host>`
   - `DB_PORT` = `3306`
   - `DB_USER` = `<your-cloud-mysql-username>`
   - `DB_PASSWORD` = `<your-cloud-mysql-password>`
   - `DB_NAME` = `<your-cloud-mysql-database-name>`
3. Click **Save Changes**. Render will automatically redeploy and connect to your MySQL database.
