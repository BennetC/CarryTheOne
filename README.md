# RT Arithmetic Trainer (Flask)

A minimal Flask web app for collecting arithmetic response-time data with per-trial metadata for modeling expected human solve times.

## Features
- Consent + participant code workflow (manual code or generated anonymous code).
- One-problem-per-page task flow with client-side response timing.
- Trial integrity checks and suspicious-trial flagging.
- Admin dashboard with summary statistics and CSV export.
- SQLite via SQLAlchemy; database is created automatically on first run.

## Requirements
- Python 3.11+

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
Set an admin password (required for `/admin`) and start the app:
```bash
export ADMIN_PASSWORD='change-me'
python app.py
```
Then open `http://127.0.0.1:5000`.

## Participant flow
1. Visit `/` and consent.
2. Enter a participant code OR click generate anonymous code.
3. Optionally add participant metadata (age, gender, dominant hand, math confidence).
4. Complete problems at `/task` by typing answers; correct answers auto-submit and load the next problem immediately.
5. Use **Stop session** at any time to end the current run and return to start.

Data saving behavior:
- Trials are saved live: each correct submission is committed immediately when posted.
- Stopping a session does not delete already submitted trials.

Optional problem controls via query params on `/task`:
- `ops=add,sub,mul`
- `scale_strategy=dynamic|polynomial|exponential|random`
- `seed=<value>` for reproducible demo generation

Example:
```text
/task?scale_strategy=dynamic&ops=add,mul&seed=demo1
```

Adaptive scaling notes:
- The app now starts with simpler questions (single-digit add/subtract), then scales into larger numbers and multiplication over time.
- `dynamic` adjusts the scaling factor from performance (recent accuracy + response times), then multiplies by a bounded dynamic multiplier between `0.2` and `2.0`.
- `polynomial` and `exponential` provide deterministic growth alternatives.
- `random` picks one of the three strategies per generated problem.
- When Flask debug mode is enabled (`app.run(debug=True)`), `/task` displays a scaling debug panel with strategy and factor diagnostics.

## Admin dashboard
- Visit `/admin` and log in with `ADMIN_PASSWORD`.
- View total participants, total trials, accuracy %, mean/median RT.
- Optional filters: operation and start/end ISO datetime.
- Export CSV at `/admin/export.csv` (with the same query parameters if filtering).

## CSV columns
`/admin/export.csv` includes:
- Trial identity: `id`, `participant_id`
- Participant metadata: `participant_age`, `participant_gender`, `participant_dominant_hand`, `participant_math_confidence`
- Problem fields: `expression_text`, `op_type`, `a`, `b`, `c`, `correct_answer`
- Response fields: `user_answer`, `is_correct`, `rt_ms`, `server_duration_ms`
- Timestamps: `started_at`, `submitted_at`, `client_start_ts`, `client_submit_ts`
- Difficulty/meta: `num_digits_total`, `carry_count`, `borrow_count`
- Input/context: `input_method`, `page_visibility_events`, `is_suspicious`

## Suspicious trial rules
A trial is flagged (`is_suspicious = true`) if any condition is true:
- `rt_ms < 250`
- `rt_ms > 60000`
- `abs(rt_ms - server_duration_ms) > 2000`

## Notes
- Multiplication uses a clear `×` symbol in display text, but all server-side values are numeric.
- Reloading `/task` creates a brand-new trial (new `id`), preventing accidental timing restarts on a reused trial.
- Task mode is optimized for uninterrupted data collection: incorrect answers are not submitted; only correct answers auto-submit and advance.
