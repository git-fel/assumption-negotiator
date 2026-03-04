"""
Claude — Flask Backend
=======================
This file is the "server" that powers the ChatGPT-lookalike web interface.

HOW FLASK WORKS (big picture):
  - Flask is a Python web server. When you run this file, it starts a server
    at http://localhost:5000 that your browser can talk to.
  - It has two jobs:
      1. Serve the HTML page (the visual interface) when you open the browser.
      2. Accept API requests from the browser (when you send a message),
         call the Anthropic API, and send the response back.

HOW THIS DIFFERS FROM STREAMLIT:
  - Streamlit ran Python in the browser. Flask separates things clearly:
      Python (this file) → handles logic and API calls on the server
      HTML/JS (index.html) → handles the visual interface in the browser
  - The browser and server talk to each other via "routes" (URL endpoints).

Run with:
    python app_flask.py

Then open your browser to:
    http://localhost:5000
"""

import json
import os
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic

# ─── App Setup ─────────────────────────────────────────────────────────────────
# Flask(__name__) creates a new web app.
# It looks for HTML templates in a folder called "templates/".
app = Flask(__name__)

# ─── API Client ────────────────────────────────────────────────────────────────
# We create the Anthropic client inside a function (get_client) rather than
# at the top of the file. This avoids a macOS issue where creating the client
# during startup — before Flask is fully running — can cause SIGTERM ("terminated").
def get_client():
    """Create and return the Anthropic client. Called only when a route is hit."""
    return Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ─── Route: Home Page ──────────────────────────────────────────────────────────
# When you visit http://localhost:5000 in your browser, Flask serves index.html.
@app.route("/")
def index():
    """Serve the main chat page."""
    return render_template("index.html")


# ─── Route: Regular Chat ───────────────────────────────────────────────────────
# The browser sends: {"messages": [{"role": "user", "content": "..."}, ...]}
# This route calls Claude and sends back: {"reply": "..."}
@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Handle a regular chat message.
    Receives the full conversation history so Claude can remember context.
    """
    data = request.json
    messages = data["messages"]

    response = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=messages,
    )
    return jsonify({"reply": response.content[0].text})


# ─── Route: Start Assumption Negotiation ───────────────────────────────────────
# The browser sends: {"query": "Should I buy oat milk or regular milk?"}
# This route calls Claude and sends back: {"recommendation": "...", "assumptions": {...}}
@app.route("/api/initial", methods=["POST"])
def initial():
    """
    Start the assumption negotiation workflow.
    Gets a recommendation + 5 assumptions from Claude.
    """
    data = request.json
    user_input = data["query"]

    response = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system="""
            You are an assistant that provides recommendations based on user queries. For each recommendation,
            also provide a list of 5 key assumptions that you made to arrive at that recommendation.
            IMPORTANT GUIDELINES FOR ASSUMPTIONS:
                - State assumptions in POSITIVE form, avoid double negatives
                - Instead of "You don't have lactose intolerance", say "You can consume dairy products without issues"
                - Instead of "Cost difference isn't a deciding factor", say "You're willing to pay more for quality"
                - Make assumptions clear and easy to confirm with yes/no

            Return ONLY valid raw JSON. No markdown, no code blocks, no extra text.
            {
                "recommendation": "X",
                "assumptions": {
                    "A1": "Assumption 1 details...",
                    "A2": "Assumption 2 details..."
                }
            }
        """,
        messages=[{"role": "user", "content": user_input}],
    )
    return jsonify(json.loads(response.content[0].text))


# ─── Route: Generate Revised Recommendation ────────────────────────────────────
# The browser sends the initial response + the user's feedback (accepted/rejected assumptions).
# This route filters to accepted assumptions, adds new ones, and asks Claude to revise.
@app.route("/api/revise", methods=["POST"])
def revise():
    """
    Generate a revised recommendation based on accepted assumptions.

    Receives:
        {
            "initial_response": {"recommendation": "...", "assumptions": {...}},
            "feedback": {
                "selected_responses": {"A1": 1, "A2": 0, ...},
                "new_assumptions": {"A6": "I have a nut allergy"}   (may be empty)
            }
        }
    """
    data = request.json
    initial_response = data["initial_response"]
    feedback = data["feedback"]

    # Build the filtered assumption set: only accepted ones (value=1) + any new ones
    accepted = {}
    for key, value in feedback["selected_responses"].items():
        if value == 1:
            accepted[key] = initial_response["assumptions"][key]
    accepted.update(feedback.get("new_assumptions", {}))

    api_response = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system="""
            You are an assistant helping a user refine their decision through assumption negotiation.

            Generate a revised recommendation that BALANCES ALL accepted assumptions and new considerations.
            - Do NOT let any single factor dominate the decision
            - Consider trade-offs between conflicting factors
            - The recommendation should reflect a holistic view of ALL accepted assumptions

            Return ONLY valid raw JSON. No markdown, no code blocks, no extra text.
            {
                "recommendation": "X",
                "assumptions": {
                    "A1": "Assumption 1 details...",
                    "A2": "Assumption 2 details..."
                }
            }
        """,
        messages=[{
            "role": "user",
            "content": f"""
                INITIAL RECOMMENDATION: {initial_response["recommendation"]}

                ACCEPTED ASSUMPTIONS (user confirmed these are correct):
                {json.dumps(accepted, indent=2)}

                Generate a revised recommendation balancing ALL these assumptions.
                No single factor should dominate — consider the trade-offs.
            """,
        }],
    )
    return jsonify(json.loads(api_response.content[0].text))


# ─── Start the Server ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # port=5001: we avoid 5000 because macOS uses it for AirPlay Receiver.
    # debug=False: macOS terminates the process when debug=True manipulates
    #   signal handlers during startup — turning it off fixes "zsh: terminated".
    # Visit http://localhost:5001 in your browser.
    app.run(host="127.0.0.1", port=5001, debug=False)
