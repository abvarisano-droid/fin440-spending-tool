# Deploying Spend Shadow to Streamlit Community Cloud

## Before you deploy

- [ ] `python -m pytest -q` passes.
- [ ] `git ls-files '*.csv'` prints only `sample_data/sample_transactions.csv`.
- [ ] `git status` is clean and everything you want live is committed to the branch you will deploy.
- [ ] No keys, tokens or account numbers in any file (the app needs none).

## Steps

1. Create a GitHub repository and push this project to it. The repo can be private: Community
   Cloud deploys private repos once your GitHub account is connected to it.
2. Go to https://share.streamlit.io, sign in with GitHub and click "Create app".
3. Pick the repository, the branch (use `main`, or the branch you want live) and set the main
   file path to `streamlit_app.py`.
4. Open "Advanced settings" and choose Python 3.12. The pins in `requirements.txt` all have
   wheels for 3.12 on Linux.
5. Leave Secrets empty. The app has no secrets, keys or environment variables.
6. Click "Deploy". The first build installs `requirements.txt` and takes a few minutes.
7. Open the app, click "Use sample data" on the Upload page, and check each page loads.

## What leaves the machine

Uploads live only in the browser session (`st.session_state`) and are never written to disk or
logged. The only outbound request is a ticker symbol and a start date sent to Yahoo Finance
(through yfinance) to fetch prices. No transaction data is sent anywhere.

## Real data

Never commit real bank CSVs. `.gitignore` blocks every `*.csv` except the fictional sample.
Upload real statements through the running app only; they are held in memory for that session.

## Updating

Pushing to the deployed branch redeploys automatically. To change a pin in `requirements.txt`,
check that the new version has a Linux wheel for your chosen Python version first.
