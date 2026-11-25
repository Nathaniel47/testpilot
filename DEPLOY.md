# Deploying the demo

**Host: Hugging Face Spaces (Gradio SDK, free CPU Basic hardware).** Visitors need no account. The
demo uses the offline generator, so it needs **no API key and no secrets**. Do not add any.

A Docker Space was the first choice, but in November 2026 the New Space form showed Docker as
**Paid** for this free account, so the demo uses Gradio.

## Test it locally first

```bash
pip install -r requirements-demo.txt
```

```bash
python -m app.gradio_app
```

## Publish (the login and any token are yours alone)

1. Sign in at https://huggingface.co.
2. New Space: name `testpilot`, SDK **Gradio**, template Blank, hardware **CPU Basic** (free),
   visibility Public. Do not pick paid hardware, storage or dev mode.
3. Build the upload folder (written to `work/space_testpilot`):

```bash
python -m app.build_space
```

4. Upload that folder's contents to the Space. With git (replace `YOUR_USER`; the password Git
   asks for is an access token with write access, from Settings, Access Tokens; never commit it):

```bash
git clone https://huggingface.co/spaces/YOUR_USER/testpilot space_push
```

```bash
cp -r work/space_testpilot/. space_push/
```

```bash
cd space_push && git add . && git commit -m "TestPilot demo" && git push
```

5. Wait for the build, then run one example on the Space page. A sleeping Space takes a while to
   wake, and a run takes roughly 10 to 60 seconds.

## Limits built into the demo

One function, at most 60 lines and 3,000 characters; only listed standard-library imports; one
scoring job at a time with a queue of 10; 8 runs per browser session with a 20 second cooldown;
no public API endpoint; time and memory limits per test run. The app does not save input.

## What protects the host

The input checks and the sandbox (separate process, empty environment, temporary folder, time and
memory limits, soft network and write guards) stop accidents and casual misuse. They are **not** a
security boundary against a determined attacker. The remaining protection is whatever isolation
Hugging Face puts around a Space, which this project does not control and has not tested. That is
why the Space must hold no secrets.
