# Deploy to Streamlit Community Cloud

This project is ready for Streamlit Cloud with:

- `streamlit_app.py` as the entrypoint
- `requirements.txt` for Python dependencies
- `.streamlit/config.toml` for basic app theme/config
- `.gitignore` to keep local database, uploads, generated reports, and secrets out of Git

## Step 1: Create a GitHub Account

1. Go to <https://github.com/signup>.
2. Create or sign in to your account.
3. Verify your email.

## Step 2: Create a New GitHub Repository

Recommended repo name:

```text
waqf-impact-intelligence-prototype
```

Choose `Private` if the prototype includes institutional or beneficiary data.

## Step 3: Push This Project

From this folder:

```bash
cd /Users/hdf/Documents/Codex/2026-06-15/files-mentioned-by-the-user-you/outputs/waqf-impact-prototype
git init
git branch -M main
git add .
git commit -m "Initial Streamlit prototype"
git remote add origin https://github.com/YOUR_USERNAME/waqf-impact-intelligence-prototype.git
git push -u origin main
```

If GitHub asks for a password, use a Personal Access Token instead of your GitHub password.

## Step 4: Create a GitHub Personal Access Token

Use a fine-grained token with the smallest permissions needed.

1. Open GitHub.
2. Click your profile photo.
3. Go to `Settings`.
4. Go to `Developer settings`.
5. Go to `Personal access tokens`.
6. Choose `Fine-grained tokens`.
7. Click `Generate new token`.
8. Set:
   - Token name: `streamlit-prototype-push`
   - Expiration: 30 or 90 days
   - Repository access: only this repository
   - Repository permissions: `Contents: Read and write`
9. Generate the token.
10. Copy it once and store it securely.

Never paste this token into the app code, GitHub repo, chat, or README.

## Step 5: Deploy on Streamlit Community Cloud

1. Go to <https://share.streamlit.io/>.
2. Sign in with GitHub.
3. Click `Create app` or `New app`.
4. Select:
   - Repository: `YOUR_USERNAME/waqf-impact-intelligence-prototype`
   - Branch: `main`
   - Main file path: `streamlit_app.py`
5. Open advanced settings if available and select a current Python version, such as Python 3.11 or 3.12.
6. Click deploy.

## Step 6: Add Secrets, If Needed

This demo does not require an AI API key. If you later add OpenAI, Claude, database, or storage credentials:

1. Open your app in Streamlit Cloud.
2. Go to app settings.
3. Open `Secrets`.
4. Add TOML values, for example:

```toml
OPENAI_API_KEY = "sk-..."
DATABASE_URL = "postgresql://..."
```

Use them in Streamlit with:

```python
st.secrets["OPENAI_API_KEY"]
```

## Important Demo Limitation

This prototype uses local SQLite. On Streamlit Cloud, local files can be reset when the app restarts. That is acceptable for a demo. For production, move the database to PostgreSQL, Supabase, Azure SQL, or another persistent service.
