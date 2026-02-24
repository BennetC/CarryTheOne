import csv
import io
import os
import random
import uuid
from datetime import datetime
from statistics import mean, median

from flask import (
    Flask,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rt_training.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


def utcnow_naive() -> datetime:
    return datetime.utcnow()


class Participant(db.Model):
    __tablename__ = "participants"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    user_agent = db.Column(db.String(512), nullable=True)
    device_hint = db.Column(db.String(128), nullable=True)


class Trial(db.Model):
    __tablename__ = "trials"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    participant_id = db.Column(db.String(36), db.ForeignKey("participants.id"), nullable=False, index=True)

    expression_text = db.Column(db.String(128), nullable=False)
    op_type = db.Column(db.String(16), nullable=False, index=True)
    a = db.Column(db.Integer, nullable=False)
    b = db.Column(db.Integer, nullable=False)
    c = db.Column(db.Integer, nullable=True)
    correct_answer = db.Column(db.Integer, nullable=False)

    user_answer = db.Column(db.String(64), nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    rt_ms = db.Column(db.Integer, nullable=True)
    server_duration_ms = db.Column(db.Integer, nullable=True)

    started_at = db.Column(db.DateTime, nullable=False, default=utcnow_naive)
    submitted_at = db.Column(db.DateTime, nullable=True)

    client_start_ts = db.Column(db.BigInteger, nullable=True)
    client_submit_ts = db.Column(db.BigInteger, nullable=True)

    num_digits_total = db.Column(db.Integer, nullable=True)
    carry_count = db.Column(db.Integer, nullable=True)
    borrow_count = db.Column(db.Integer, nullable=True)

    input_method = db.Column(db.String(32), nullable=True)
    page_visibility_events = db.Column(db.Integer, nullable=True)
    is_suspicious = db.Column(db.Boolean, nullable=False, default=False)


def detect_device_hint(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "mobile" in ua:
        return "mobile"
    if "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "desktop"


def random_code() -> str:
    return str(uuid.uuid4())[:8]


def count_carries(a: int, b: int) -> int:
    carries = 0
    carry = 0
    x, y = abs(a), abs(b)
    while x > 0 or y > 0:
        da = x % 10
        db_ = y % 10
        if da + db_ + carry >= 10:
            carries += 1
            carry = 1
        else:
            carry = 0
        x //= 10
        y //= 10
    return carries


def count_borrows(a: int, b: int) -> int:
    borrows = 0
    borrow = 0
    x, y = a, b
    while x > 0 or y > 0:
        da = x % 10
        db_ = y % 10
        da -= borrow
        if da < db_:
            borrows += 1
            borrow = 1
        else:
            borrow = 0
        x //= 10
        y //= 10
    return borrows


def pick_in_range(rng: random.Random, digits_min: int, digits_max: int) -> int:
    digits = rng.randint(digits_min, digits_max)
    low = 10 ** (digits - 1)
    high = (10**digits) - 1
    if digits == 1:
        low = 0
    return rng.randint(low, high)


def generate_problem(difficulty: str = "medium", operations=None, seed=None):
    operations = operations or ["add", "sub", "mul"]
    operations = [o for o in operations if o in {"add", "sub", "mul"}] or ["add", "sub", "mul"]

    rng = random.Random(seed) if seed is not None else random.Random()
    op = rng.choice(operations)

    if difficulty == "easy":
        add_digits = (1, 2)
        sub_digits = (1, 2)
        mul_left, mul_right = (1, 1), (1, 2)
    elif difficulty == "hard":
        add_digits = (3, 4)
        sub_digits = (3, 4)
        mul_left, mul_right = (2, 2), (3, 3)
    else:
        add_digits = (2, 3)
        sub_digits = (2, 3)
        mul_left, mul_right = (2, 2), (2, 2)

    if op == "add":
        a = pick_in_range(rng, *add_digits)
        b = pick_in_range(rng, *add_digits)
        expression_text = f"{a} + {b}"
        correct_answer = a + b
        carry_count = count_carries(a, b)
        borrow_count = None
    elif op == "sub":
        x = pick_in_range(rng, *sub_digits)
        y = pick_in_range(rng, *sub_digits)
        a, b = max(x, y), min(x, y)
        expression_text = f"{a} - {b}"
        correct_answer = a - b
        carry_count = None
        borrow_count = count_borrows(a, b)
    else:
        a = pick_in_range(rng, *mul_left)
        b = pick_in_range(rng, *mul_right)
        expression_text = f"{a} × {b}"
        correct_answer = a * b
        carry_count = len(str(abs(a)))
        borrow_count = len(str(abs(b)))

    num_digits_total = len(str(abs(a))) + len(str(abs(b)))

    return {
        "expression_text": expression_text,
        "op_type": op,
        "a": a,
        "b": b,
        "c": None,
        "correct_answer": correct_answer,
        "num_digits_total": num_digits_total,
        "carry_count": carry_count,
        "borrow_count": borrow_count,
    }


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def progression_cap(solved_count: int) -> float:
    if solved_count <= 2:
        return 1.6
    if solved_count <= 5:
        return 2.1
    if solved_count <= 10:
        return 2.8
    if solved_count <= 20:
        return 3.8
    if solved_count <= 35:
        return 5.0
    if solved_count <= 50:
        return 6.2
    return 7.2


def infer_scaling_factor(participant_id: str, strategy: str):
    completed_trials = (
        Trial.query.filter_by(participant_id=participant_id)
        .filter(Trial.submitted_at.isnot(None))
        .order_by(Trial.started_at.asc())
        .all()
    )
    solved_count = len(completed_trials)

    recent = completed_trials[-10:]
    accuracy = (sum(1 for t in recent if t.is_correct) / len(recent)) if recent else 1.0

    recent_rt_values = [t.rt_ms for t in recent if t.rt_ms is not None]
    avg_recent_rt = mean(recent_rt_values) if recent_rt_values else 5500
    speed_ratio = clamp(4000 / max(avg_recent_rt, 800), 0.0, 1.2)

    timeout_penalty = sum(1 for t in recent if t.rt_ms is not None and t.rt_ms > 12000) * 0.06
    incorrect_penalty = sum(1 for t in recent if not t.is_correct) * 0.08
    streak_bonus = 0.1 if recent and all(t.is_correct for t in recent[-3:]) else 0.0

    strategy_key = (strategy or "dynamic").lower()
    used_strategy = strategy_key
    if strategy_key == "random":
        used_strategy = random.choice(["polynomial", "exponential", "dynamic"])

    if used_strategy == "polynomial":
        scaling_factor = 1 + (solved_count / 10) ** 1.4
    elif used_strategy == "exponential":
        scaling_factor = 1.03**solved_count
    else:
        base_factor = 1 + (solved_count / 12) ** 1.35
        dynamic_multiplier = clamp(
            0.75 + (accuracy * 0.45) + (speed_ratio * 0.35) + streak_bonus - timeout_penalty - incorrect_penalty,
            0.5,
            1.5,
        )
        scaling_factor = base_factor * dynamic_multiplier

    capped_factor = clamp(scaling_factor, 1.0, progression_cap(solved_count))
    return {
        "solved_count": solved_count,
        "accuracy_recent": round(accuracy, 3),
        "avg_recent_rt": round(avg_recent_rt, 2),
        "speed_ratio": round(speed_ratio, 3),
        "scaling_factor": round(capped_factor, 3),
        "strategy": used_strategy,
    }


def generate_scaled_problem(operations, scaling_factor: float, seed=None):
    operations = operations or ["add", "sub", "mul"]
    operations = [o for o in operations if o in {"add", "sub", "mul"}] or ["add", "sub", "mul"]
    rng = random.Random(seed) if seed is not None else random.Random()

    if scaling_factor < 1.5:
        allowed_ops = ["add", "sub"]
        add_digits = (1, 1)
        sub_digits = (1, 1)
        mul_left, mul_right = (1, 1), (1, 1)
    elif scaling_factor < 2.8:
        allowed_ops = ["add", "sub"]
        add_digits = (1, 2)
        sub_digits = (1, 2)
        mul_left, mul_right = (1, 1), (1, 1)
    elif scaling_factor < 3.8:
        allowed_ops = ["add", "sub", "mul"]
        add_digits = (2, 2)
        sub_digits = (2, 2)
        mul_left, mul_right = (1, 1), (1, 2)
    elif scaling_factor < 5.0:
        allowed_ops = ["add", "sub", "mul"]
        add_digits = (2, 3)
        sub_digits = (2, 3)
        mul_left, mul_right = (2, 2), (1, 2)
    elif scaling_factor < 6.5:
        allowed_ops = ["add", "sub", "mul"]
        add_digits = (3, 3)
        sub_digits = (3, 3)
        mul_left, mul_right = (2, 2), (2, 2)
    else:
        allowed_ops = ["add", "sub", "mul"]
        add_digits = (3, 4)
        sub_digits = (3, 4)
        mul_left, mul_right = (2, 3), (2, 3)

    eligible_ops = [op for op in operations if op in allowed_ops]
    if not eligible_ops:
        eligible_ops = ["add", "sub"] if scaling_factor < 2.5 else operations

    op = rng.choice(eligible_ops)

    if op == "add":
        a = pick_in_range(rng, *add_digits)
        b = pick_in_range(rng, *add_digits)
        expression_text = f"{a} + {b}"
        correct_answer = a + b
        carry_count = count_carries(a, b)
        borrow_count = None
    elif op == "sub":
        x = pick_in_range(rng, *sub_digits)
        y = pick_in_range(rng, *sub_digits)
        a, b = max(x, y), min(x, y)
        expression_text = f"{a} - {b}"
        correct_answer = a - b
        carry_count = None
        borrow_count = count_borrows(a, b)
    else:
        a = pick_in_range(rng, *mul_left)
        b = pick_in_range(rng, *mul_right)
        expression_text = f"{a} × {b}"
        correct_answer = a * b
        carry_count = len(str(abs(a)))
        borrow_count = len(str(abs(b)))

    num_digits_total = len(str(abs(a))) + len(str(abs(b)))
    return {
        "expression_text": expression_text,
        "op_type": op,
        "a": a,
        "b": b,
        "c": None,
        "correct_answer": correct_answer,
        "num_digits_total": num_digits_total,
        "carry_count": carry_count,
        "borrow_count": borrow_count,
    }


def get_or_create_participant(code: str):
    code = code.strip()
    existing = Participant.query.filter_by(code=code).first()
    if existing:
        return existing

    p = Participant(
        code=code,
        user_agent=request.headers.get("User-Agent", "")[:512],
        device_hint=detect_device_hint(request.headers.get("User-Agent", "")),
    )
    db.session.add(p)
    db.session.commit()
    return p


def get_current_participant():
    pid = session.get("participant_id")
    if not pid:
        return None
    return Participant.query.get(pid)


def require_admin():
    return bool(session.get("admin_authed"))


def parse_iso_naive(value: str):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if request.form.get("consent") != "yes":
            flash("You must agree to participate before starting.")
            return render_template("index.html")

        code = (request.form.get("code") or "").strip()
        if "generate" in request.form or not code:
            code = random_code()

        participant = get_or_create_participant(code)
        session["participant_id"] = participant.id

        resp = make_response(redirect(url_for("task")))
        resp.set_cookie("participant_code", participant.code, max_age=60 * 60 * 24 * 365)
        return resp

    existing_code = request.cookies.get("participant_code", "")
    return render_template("index.html", existing_code=existing_code)


@app.route("/task", methods=["GET", "POST"])
def task():
    participant = get_current_participant()
    if not participant:
        return redirect(url_for("index"))

    if request.method == "POST":
        trial_id = request.form.get("trial_id", "")
        trial = Trial.query.filter_by(id=trial_id, participant_id=participant.id).first()
        if not trial or trial.submitted_at is not None:
            flash("Trial not found or already submitted. Please try a new problem.")
            return redirect(url_for("task"))

        user_answer = (request.form.get("user_answer") or "").strip()
        rt_ms = request.form.get("rt_ms", type=int)
        client_start_ts = request.form.get("client_start_ts", type=int)
        client_submit_ts = request.form.get("client_submit_ts", type=int)
        visibility_events = request.form.get("visibility_events", type=int)
        input_method = (request.form.get("input_method") or "keyboard").strip()[:32]

        trial.submitted_at = utcnow_naive()
        trial.user_answer = user_answer
        trial.rt_ms = rt_ms
        trial.client_start_ts = client_start_ts
        trial.client_submit_ts = client_submit_ts
        trial.page_visibility_events = visibility_events
        trial.input_method = input_method

        try:
            parsed = int(user_answer)
            trial.is_correct = parsed == trial.correct_answer
        except ValueError:
            trial.is_correct = False

        if trial.started_at is not None and trial.submitted_at is not None:
            trial.server_duration_ms = int((trial.submitted_at - trial.started_at).total_seconds() * 1000)
        else:
            trial.server_duration_ms = None

        suspicious = False
        if rt_ms is None or rt_ms < 250 or rt_ms > 60000:
            suspicious = True
        if rt_ms is not None and trial.server_duration_ms is not None and abs(rt_ms - trial.server_duration_ms) > 2000:
            suspicious = True
        trial.is_suspicious = suspicious

        db.session.commit()
        session["last_trial_id"] = trial.id

        # Auto-advance flow: successful submissions go straight to the next problem.
        return redirect(url_for("task"))

    ops_param = (request.args.get("ops") or "add,sub,mul").lower().split(",")
    scale_strategy = (request.args.get("scale_strategy") or "dynamic").lower()
    seed = request.args.get("seed")
    scale_meta = infer_scaling_factor(participant.id, scale_strategy)
    problem = generate_scaled_problem(
        operations=ops_param,
        scaling_factor=scale_meta["scaling_factor"],
        seed=seed,
    )

    trial = Trial(
        participant_id=participant.id,
        started_at=utcnow_naive(),
        **problem,
    )
    db.session.add(trial)
    db.session.commit()

    return render_template(
        "task.html",
        trial=trial,
        ops=",".join(ops_param),
        scale_strategy=scale_strategy,
        scale_meta=scale_meta,
        debug_mode=app.debug,
        seed=seed,
    )


@app.route("/feedback")
def feedback():
    participant = get_current_participant()
    if not participant:
        return redirect(url_for("index"))

    trial_id = session.get("last_trial_id")
    if not trial_id:
        return redirect(url_for("task"))

    trial = Trial.query.filter_by(id=trial_id, participant_id=participant.id).first()
    if not trial or trial.submitted_at is None:
        return redirect(url_for("task"))

    return render_template("feedback.html", trial=trial)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        return "ADMIN_PASSWORD environment variable is not set.", 500

    if request.method == "POST" and request.form.get("admin_password"):
        if request.form.get("admin_password") == admin_password:
            session["admin_authed"] = True
            return redirect(url_for("admin"))
        flash("Invalid admin password")

    if not require_admin():
        return render_template("admin.html", show_login=True)

    op_type = request.args.get("op_type", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    start_dt = parse_iso_naive(start_date)
    end_dt = parse_iso_naive(end_date)

    trials_query = Trial.query.filter(Trial.submitted_at.isnot(None))
    if op_type:
        trials_query = trials_query.filter_by(op_type=op_type)
    if start_dt:
        trials_query = trials_query.filter(Trial.submitted_at >= start_dt)
    if end_dt:
        trials_query = trials_query.filter(Trial.submitted_at <= end_dt)

    trials = trials_query.all()
    rt_values = [t.rt_ms for t in trials if t.rt_ms is not None]
    correct_count = sum(1 for t in trials if t.is_correct)

    stats = {
        "participants": Participant.query.count(),
        "trials": len(trials),
        "accuracy": round((correct_count / len(trials) * 100), 2) if trials else 0,
        "mean_rt": round(mean(rt_values), 2) if rt_values else None,
        "median_rt": round(median(rt_values), 2) if rt_values else None,
    }

    op_counts = (
        db.session.query(Trial.op_type, func.count(Trial.id))
        .filter(Trial.submitted_at.isnot(None))
        .group_by(Trial.op_type)
        .all()
    )

    return render_template(
        "admin.html",
        show_login=False,
        stats=stats,
        op_counts=op_counts,
        op_type=op_type,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/admin/export.csv")
def export_csv():
    if not require_admin():
        return redirect(url_for("admin"))

    op_type = request.args.get("op_type", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    start_dt = parse_iso_naive(start_date)
    end_dt = parse_iso_naive(end_date)

    trials_query = Trial.query
    if op_type:
        trials_query = trials_query.filter_by(op_type=op_type)
    if start_dt:
        trials_query = trials_query.filter(Trial.submitted_at >= start_dt)
    if end_dt:
        trials_query = trials_query.filter(Trial.submitted_at <= end_dt)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "participant_id",
            "expression_text",
            "op_type",
            "a",
            "b",
            "c",
            "correct_answer",
            "user_answer",
            "is_correct",
            "rt_ms",
            "server_duration_ms",
            "started_at",
            "submitted_at",
            "client_start_ts",
            "client_submit_ts",
            "num_digits_total",
            "carry_count",
            "borrow_count",
            "input_method",
            "page_visibility_events",
            "is_suspicious",
        ]
    )

    for t in trials_query.order_by(Trial.started_at.asc()).all():
        writer.writerow(
            [
                t.id,
                t.participant_id,
                t.expression_text,
                t.op_type,
                t.a,
                t.b,
                t.c,
                t.correct_answer,
                t.user_answer,
                t.is_correct,
                t.rt_ms,
                t.server_duration_ms,
                t.started_at,
                t.submitted_at,
                t.client_start_ts,
                t.client_submit_ts,
                t.num_digits_total,
                t.carry_count,
                t.borrow_count,
                t.input_method,
                t.page_visibility_events,
                t.is_suspicious,
            ]
        )

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=trials_export.csv"
    return response


@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Initialized the database.")


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
