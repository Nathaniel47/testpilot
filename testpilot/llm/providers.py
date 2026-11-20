"""Thin wrappers over the Groq and Gemini SDKs. Imported lazily so offline runs need neither."""

from dataclasses import dataclass

from testpilot import config


@dataclass
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def groq_complete(model, system, prompt, temperature, seed, max_tokens) -> Completion:
    from groq import Groq

    key = config.groq_api_key()
    if not key:
        raise RuntimeError("TESTPILOT_GROQ_API_KEY is not set")
    resp = Groq(api_key=key).chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=temperature,
        seed=seed,
        max_tokens=max_tokens,
    )
    use = resp.usage
    text = resp.choices[0].message.content or ""
    return Completion(text, use.prompt_tokens, use.completion_tokens)


def gemini_complete(model, system, prompt, temperature, seed, max_tokens) -> Completion:
    from google import genai
    from google.genai import types

    key = config.gemini_api_key()
    if not key:
        raise RuntimeError("TESTPILOT_GEMINI_API_KEY is not set")
    resp = genai.Client(api_key=key).models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            seed=seed,
            max_output_tokens=max_tokens,
        ),
    )
    use = resp.usage_metadata
    return Completion(resp.text or "", use.prompt_token_count or 0, use.candidates_token_count or 0)


PROVIDERS = {"groq": groq_complete, "gemini": gemini_complete}
