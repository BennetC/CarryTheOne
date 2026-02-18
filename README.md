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
3. Complete problems at `/task` and view immediate results at `/feedback`.

Optional problem controls via query params on `/task`:
- `difficulty=easy|medium|hard`
- `ops=add,sub,mul`
- `seed=<value>` for reproducible demo generation

Example:
```text
/task?difficulty=hard&ops=add,mul&seed=demo1
```

## Admin dashboard
- Visit `/admin` and log in with `ADMIN_PASSWORD`.
- View total participants, total trials, accuracy %, mean/median RT.
- Optional filters: operation and start/end ISO datetime.
- Export CSV at `/admin/export.csv` (with the same query parameters if filtering).

## CSV columns
`/admin/export.csv` includes:
- Trial identity: `id`, `participant_id`
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
