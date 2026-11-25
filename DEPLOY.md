# Deploying the demo

**Host: a static Hugging Face Space.** Visitors need no account. The page shows results that the
real pipeline saved for three examples. It runs no code, so it needs **no API key and no
secrets**.

Why static (what the New Space form and ZeroGPU showed on a free account in November 2026):

- Docker was marked **Paid**.
- Gradio ran only on **ZeroGPU**; free CPU Basic needed PRO.
- ZeroGPU stopped this app at startup with "No @spaces.GPU function detected during startup",
  because TestPilot uses no GPU. We did not work around that check.

## How the page gets its content

The Space holds `README.md` and `index.html`. `index.html` loads `app/static/page.js` from this
public GitHub repository through jsDelivr, pinned to one commit, and the script loads
`results.json` from the same place. The page changes only when `index.html` points to a new commit.
It depends on GitHub and jsDelivr being available.

## Update the demo

1. If the examples or the pipeline changed, regenerate the saved results:

```bash
python -m app.build_static results
```

2. Run `pytest`, then commit and push.
3. Write the Space files, pinned to the commit you just pushed (output in
   `work/space_testpilot`):

```bash
python -m app.build_static space
```

4. In the Space's **Files** tab, edit `index.html` and `README.md` to match those two files. The
   web editor needs only your normal sign-in. No access token is needed.

## First-time setup

Sign in at https://huggingface.co, then New Space: name `testpilot`, SDK **Static**, visibility
Public. Then do the steps above.

## Run the interactive version locally

Pasting your own function works only on your machine:

```bash
pip install -r requirements-demo.txt
```

```bash
python -m testpilot.demo.page
```

It limits input (one function, at most 60 lines and 3,000 characters, listed standard-library
imports only) and runs code with time and memory limits. These checks are **not** a security
boundary, so do not expose it publicly without real isolation.
