import uuid
from flask import Flask, request, jsonify
from llm_signal import llm_classify
from stylometric_signal import stylometric_classify
from scoring import combine_scores, get_label
from audit_log import log_event, read_log

app = Flask(__name__)


@app.route("/submit", methods=["POST"])
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


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": read_log()})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
