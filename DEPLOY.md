# Deploying the demo

**Host: Hugging Face Spaces (Docker SDK).** Free, no sign-up for visitors, and the container
isolates the visitor-pasted code. (Streamlit Community Cloud has no container boundary for
running untrusted code, so it was not chosen.) The demo uses the offline generator, so it needs
**no API key and no secrets**.

## Test it locally first

```bash
pip install -r requirements-demo.txt
streamlit run app/streamlit_app.py
```

Optional, to test the container: `docker build -f app/space/Dockerfile -t testpilot-demo .` then
`docker run --rm -p 7860:7860 --read-only --tmpfs /tmp --cap-drop ALL testpilot-demo`.

## Publish (needs your Hugging Face login: steps 1 and 2 are yours)

1. Create a free account at https://huggingface.co and an access token with **write** access
   (Settings, Access Tokens). Keep the token private; never commit it.
2. Create a Space: New Space, name `testpilot`, SDK **Docker** (blank), visibility Public.
3. Build the Space folder and push it (replace `YOUR_USER`; Git asks for your username and the
   token as the password):

```bash
git clone https://huggingface.co/spaces/YOUR_USER/testpilot space_testpilot
cp app/space/Dockerfile app/space/README.md space_testpilot/
cp requirements.txt requirements-demo.txt space_testpilot/
cp -r testpilot app space_testpilot/
mkdir -p space_testpilot/results && cp results/evaluation.md space_testpilot/results/
cd space_testpilot && git add . && git commit -m "TestPilot demo" && git push
```

4. Wait for the Space to build (a few minutes). The first visit after a sleep takes about 30
   seconds to wake; the page then loads in a few seconds, and a run takes roughly 10 to 40 s.
5. Put the Space URL in the README.

## Limits built into the demo

One function, at most 60 lines and 3,000 characters; only safe standard-library imports
(math, re, itertools, ...); one scoring job at a time; 8 runs per browser session with a 20 s
cooldown; time and memory limits per test run. No input is stored.
