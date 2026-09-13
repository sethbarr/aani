# Gemini extraction setup

Gemini is supported through Google's current Interactions REST API. The
adapter sends the existing extraction prompt, source blocks and Pydantic JSON
schema, then passes the response through the same local grounding checks.
No new SDK or dependency installation is needed.

## Configure the key

Create or select a Gemini API key in
[Google AI Studio](https://aistudio.google.com/api-keys). Add these settings to
the existing `.env` file in the repository root:

```ini
EXTRACTION_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash
```

Replace the placeholder locally; do not paste the key into chat or commit it.
Add these entries to the existing file rather than replacing other settings.
The loader does not overwrite exported shell variables. This adapter prefers
`GEMINI_API_KEY` and supports `GOOGLE_API_KEY` as a fallback. The API key is
sent in the `x-goog-api-key` header, never in a URL or cached request descriptor.

`gemini-3.8-flash` is the stable model used in Google's current structured-output
guide. `GEMINI_MODEL` or `--model MODEL` can select another model available to
the project; there is no automatic provider or model fallback.
[Model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

## Test the first screened paper

Run from the repository root:

```bash
.venv/bin/python -m scripts.extract --provider gemini --model --screening config/pilot_screening.json --limit-papers 1 --output data/interim/extraction_gemini_smoke
```

This sends both chunks of the first included paper. Check
`data/interim/extraction_gemini_smoke/metrics.json` and inspect the evidence
quotes in `observations.jsonl`. An empty but valid model response is distinct
from a failed request. Incomplete responses, missing model text and malformed
JSON remain failures; they never become zero-observation successes.

The key is now configured. Live requests confirmed authentication, model access
and schema acceptance. With low thinking and a 32,768-token cap, both smoke
chunks completed and returned four candidates. Two passed automatic grounding
checks, but semantic review excluded both: one quotes E. grandis seedlings
being offered, and the other quotes Acalypha leaves being provisioned for colony
maintenance. Neither quote reports observed acceptance. The other two
candidates failed the plant-in-quote check.

The original outputs remain unchanged. Review decisions are stored separately
in `data/interim/extraction_gemini_smoke/semantic_review.json`; the corresponding
`semantic_review_observations.jsonl` is empty. Automatic grounding validation
does not establish biological or semantic validity. The treated candidates
were labelled as treated but failed grounding, so this smoke does not verify
downstream treatment exclusion.

The initial medium-thinking, 16,384-token run is preserved at
`data/interim/extraction_gemini_smoke_medium_16384/`: one chunk completed and
one exhausted its output budget. See [pilot status](pilot_status.md) for the
review findings.

## Run the screened pilot

The full pilot is complete: 20/20 jobs succeeded, returning 47 candidates.
Of 35 automatic passes, source review retained six acceptance records, excluded
26 from the primary evidence table and left three pending. There is no retained
rejection record yet. The exact execution command was:

```bash
.venv/bin/python -m scripts.extract --provider gemini --model --screening config/pilot_screening.json --output data/interim/extraction_gemini
```

The 10 included papers produce 20 jobs. Successful smoke requests are reused
from `data/raw/` even when the output directory changes. Add `--offline` to
replay cached results without a key. Keep the provider, model and inputs the
same, including generation settings, for a cache hit.

The full offline replay matched the live automatic outputs exactly. Source
decisions remain separate in `semantic_review.json`; use
`semantic_review_observations.jsonl` for the six retained records, pending
taxonomic resolution. Review the [pilot status](pilot_status.md) before a
downstream join. No prompt or schema change was made for this full run.

The separately retrieved Crumière 2021 paper remains a targeted extension:

```bash
.venv/bin/python -m scripts.extract --provider gemini --model --corpus data/interim/corpus_targeted_crumiere --output data/interim/extraction_gemini_targeted_crumiere
```

## API contract and audit

The endpoint is
`https://generativelanguage.googleapis.com/v1beta/interactions`, as documented
in Google's current [structured-output guide](https://ai.google.dev/gemini-api/docs/structured-output).
The request uses `store=false`, `system_instruction`, and a `response_format`
with `type=text`, `mime_type=application/json` and the unmodified schema.
Generation uses low thinking and a 32,768-token cap, including thought tokens,
with no thought summaries. The initial medium/16,384 configuration exhausted
its budget on the first chunk. Google explains that the cap includes reasoning
and recommends lowering thinking to reduce truncation in its
[thinking guide](https://ai.google.dev/gemini-api/docs/thinking).
The full settings are retained in each raw request cache.

Only `status=completed` with text from `model_output` steps is accepted for
parsing. Provider, requested model, returned model, response ID, request hash
and token usage are retained. API envelopes are saved in `responses/`; the raw
cache contains the complete response. The [Interactions reference](https://ai.google.dev/api/interactions-api)
defines these fields. Provider changes do not change the frozen potency,
behavioural eligibility or inference rules.

Local verification: 33 tests and Ruff pass. The frozen analysis files still
match protocol commit `98b5e09199a5eef0c46be452793e953f5a2af31e`.

Daily `quota_exceeded` errors stop immediately. Temporary rate limits receive
bounded retries with backoff; a remaining HTTP 429 stops the rest of the batch.
Authentication, permission and invalid-request errors also stop further calls.
Check the key's API project and quota in AI Studio if the service rejects the
request. [Google error reference](https://ai.google.dev/gemini-api/docs/api-errors).
