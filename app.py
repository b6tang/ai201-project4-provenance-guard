import uuid
from flask import Flask, request, jsonify
from llm_signal import llm_classify

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
    except Exception as e:
        return jsonify({"error": f"Classification failed: {str(e)}"}), 500

    if llm_ai_likelihood >= 0.5:
        attribution = "likely_ai"
        confidence = llm_ai_likelihood
        label = "Preliminary result: this text may be AI-generated. A second signal is still pending."
    else:
        attribution = "likely_human"
        confidence = 1 - llm_ai_likelihood
        label = "Preliminary result: this text may be human-written. A second signal is still pending."

    return jsonify({
        "content_id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "llm_ai_likelihood": llm_ai_likelihood,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "status": "classified",
    })


if __name__ == "__main__":
    app.run(port=5000, debug=True)
