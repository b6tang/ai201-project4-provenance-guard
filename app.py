import uuid
from flask import Flask, request, jsonify, render_template_string
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from llm_signal import llm_classify
from stylometric_signal import stylometric_classify
from scoring import combine_scores, get_label
from audit_log import log_event, read_log, find_classification, get_analytics

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute; 100 per day")
def submit():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' must be a non-empty string."}), 400

    if not creator_id or not isinstance(creator_id, str) or not creator_id.strip():
        return jsonify({"error": "'creator_id' must be a non-empty string."}), 400

    try:
        llm_ai_likelihood = llm_classify(text)
        stylometric_ai_likelihood = stylometric_classify(text)
    except Exception as e:
        return jsonify({"error": f"Classification failed: {str(e)}"}), 500

    scores = combine_scores(llm_ai_likelihood, stylometric_ai_likelihood)

    attribution = scores["attribution"]
    combined_ai_score = scores["combined_ai_score"]
    confidence = max(combined_ai_score, 1 - combined_ai_score)

    label = get_label(attribution)

    content_id = str(uuid.uuid4())

    log_event({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "llm_ai_likelihood": llm_ai_likelihood,
        "stylometric_ai_likelihood": stylometric_ai_likelihood,
        "raw_ai_likelihood": scores["raw_ai_likelihood"],
        "signal_disagreement": scores["signal_disagreement"],
        "combined_ai_score": combined_ai_score,
        "label": label,
        "status": "classified",
    })

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "llm_ai_likelihood": llm_ai_likelihood,
        "stylometric_ai_likelihood": stylometric_ai_likelihood,
        "raw_ai_likelihood": scores["raw_ai_likelihood"],
        "signal_disagreement": scores["signal_disagreement"],
        "combined_ai_score": combined_ai_score,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "status": "classified",
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id or not isinstance(content_id, str) or not content_id.strip():
        return jsonify({"error": "'content_id' must be a non-empty string."}), 400

    if not creator_reasoning or not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return jsonify({"error": "'creator_reasoning' must be a non-empty string."}), 400

    original = find_classification(content_id)
    if original is None:
        return jsonify({"error": f"No classified submission found for content_id '{content_id}'."}), 404

    log_event({
        "event_type": "appeal",
        "content_id": content_id,
        "creator_id": original["creator_id"],
        "creator_reasoning": creator_reasoning,
        "status": "under_review",
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal submitted and queued for review.",
    })


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": read_log()})


@app.route("/analytics", methods=["GET"])
def analytics():
    metrics = get_analytics()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Analytics Dashboard</title>
        <style>
            body { font-family: sans-serif; margin: 20px; }
            .card { border: 1px solid #ccc; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .metric { font-size: 24px; font-weight: bold; color: #0066cc; }
            .label { font-size: 12px; color: #666; text-transform: uppercase; }
            .verdict-row { display: flex; gap: 30px; }
            .verdict-item { text-align: center; }
        </style>
    </head>
    <body>
        <h1>Analytics Dashboard</h1>

        <div class="card">
            <div class="label">Total Classifications</div>
            <div class="metric">{{ total }}</div>
        </div>

        <div class="card">
            <div class="label">Appeal Rate</div>
            <div class="metric">{{ appeal_pct }}%</div>
        </div>

        <div class="card">
            <div class="label">Average Confidence</div>
            <div class="metric">{{ avg_conf }}</div>
        </div>

        <div class="card">
            <div class="label">Detection Pattern Counts</div>
            <div class="verdict-row">
                <div class="verdict-item">
                    <strong>Likely AI</strong><br>{{ likely_ai }}
                </div>
                <div class="verdict-item">
                    <strong>Likely Human</strong><br>{{ likely_human }}
                </div>
                <div class="verdict-item">
                    <strong>Uncertain</strong><br>{{ uncertain }}
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return render_template_string(
        html,
        total=metrics["total_classifications"],
        appeal_pct=round(metrics["appeal_rate"] * 100, 1),
        avg_conf="N/A" if metrics["average_confidence"] is None else f"{metrics['average_confidence']:.3f}",
        likely_ai=metrics["verdict_counts"]["likely_ai"],
        likely_human=metrics["verdict_counts"]["likely_human"],
        uncertain=metrics["verdict_counts"]["uncertain"],
    )


if __name__ == "__main__":
    app.run(port=5000, debug=True)
