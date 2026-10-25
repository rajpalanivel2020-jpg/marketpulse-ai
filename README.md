# MarketPulse AI — today's-news-only prototype

A guided, free-first web app prototype for scanning market-related RSS news and filtering strictly to today's date in `Asia/Kolkata`.

## Important behavior

- The date window is computed on the server each time the app loads: local midnight today inclusive, local midnight tomorrow exclusive.
- Publication timestamps are required. The app deliberately does **not** substitute `updated`, fetch time, or crawl time for a missing publication time.
- Naive timestamps with no timezone are rejected because converting them safely is ambiguous.
- Articles outside today's IST date window are rejected.
- There is no previous-day fallback.
- Original links from the feed entries are shown. Some aggregators may supply redirect links; verify critical reports on the publisher's site.
- The default impact assessment is heuristic, not a fully validated financial model.
- Optional Gemini analysis is available if you supply your own API key; free-tier availability and quotas are controlled by Google and can change.

## Run locally (Windows / Mac / Linux)

1. Install Python 3.10 or newer from https://www.python.org/downloads/
2. Extract this folder.
3. Open a terminal in this folder.
4. Create a virtual environment:

   Windows:
   ```bash
   py -m venv .venv
   .venv\Scripts\activate
   ```

   macOS/Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

5. Install packages:
   ```bash
   pip install -r requirements.txt
   ```
6. Start the app:
   ```bash
   streamlit run app.py
   ```
7. Open the local URL printed in the terminal (usually http://localhost:8501).

## Optional Gemini AI

Set `GEMINI_API_KEY` as an environment variable before starting Streamlit. Never paste API keys into `app.py` or publish them in a public repository.

Windows PowerShell (current terminal only):
```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

macOS/Linux:
```bash
export GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

Then enable “Use Gemini AI analysis” in the sidebar.

## Limitations to address next

1. Verify RSS endpoints and terms before public deployment; feeds may change or restrict automated access.
2. Add stronger publisher-specific timestamp parsing and tests.
3. Replace heuristic categorization/impact logic with structured AI analysis and evidence tracking.
4. Add a persistent database, source health monitoring, article-level provenance, and alerting.
5. Deploy with secrets configured in the hosting platform. Keep API keys server-side.
6. Test whether each source's feed link is a direct publisher link or an aggregator redirect.
