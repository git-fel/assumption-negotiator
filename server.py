"""
Claude — Web Server (no Flask required)
=========================================
This file runs the ChatGPT-style chat interface using Python's built-in
web server. No Flask, no extra setup — just standard Python + anthropic.

HOW IT WORKS:
  Python has a built-in module called `http.server` that can serve web pages
  and respond to browser requests. We use it here instead of Flask so there
  are no extra dependencies to install or configure.

  When you run this file, it:
    1. Opens a local web server at http://localhost:5001
    2. Serves the chat interface (templates/index.html) in your browser
    3. Handles API requests (when you send a message) by calling Claude
    4. Returns Claude's response back to the browser as JSON

Run with:
    python server.py

Then open your browser to:
    http://localhost:5001
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from anthropic import Anthropic


# ─── Request Handler ───────────────────────────────────────────────────────────
# This class defines what the server does when the browser makes a request.
# "GET" requests serve the HTML page. "POST" requests call the Anthropic API.
class ChatHandler(BaseHTTPRequestHandler):
    # Use HTTP/1.1 so the browser supports streaming (keep-alive connections).
    # The default is HTTP/1.0, which can cause browsers to buffer the entire
    # response before reading it — breaking SSE streaming.
    protocol_version = "HTTP/1.1"

    # ── Serve the HTML page ────────────────────────────────────────────────────
    def do_GET(self):
        """
        Called when the browser visits http://localhost:5001
        Reads index.html from the templates folder and sends it to the browser.
        """
        try:
            # Build the path to the HTML file relative to this script's location
            base_dir = os.path.dirname(os.path.abspath(__file__))
            html_path = os.path.join(base_dir, "templates", "index.html")

            with open(html_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self._send_error(404, "templates/index.html not found")

    # ── Handle API calls from the browser ─────────────────────────────────────
    def do_POST(self):
        """
        Called when the browser sends a chat message or assumption feedback.
        Reads the JSON body, calls the Anthropic API, and returns the response.
        """
        # Read the JSON data sent by the browser
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        # Create the Anthropic client (uses your ANTHROPIC_API_KEY env variable)
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Route to the correct handler based on the URL path
        if self.path == "/api/chat":
            # Chat uses streaming — it manages its own response, so we return early
            self._stream_chat(client, body)
            return

        elif self.path == "/api/initial":
            result = self._handle_initial(client, body)

        elif self.path == "/api/revise":
            result = self._handle_revise(client, body)

        else:
            self._send_error(404, f"Unknown route: {self.path}")
            return

        self._send_json(result)

    # ── Route: Regular Chat (streaming) ───────────────────────────────────────
    def _stream_chat(self, client, body):
        """
        Stream Claude's reply token-by-token using Server-Sent Events (SSE).

        WHAT IS SSE?
          Instead of waiting for Claude to finish and sending one big response,
          we keep the connection open and send small pieces of text as they arrive.
          This is exactly how ChatGPT shows text appearing word-by-word.

        SSE FORMAT (what we send to the browser):
          Each chunk looks like:   data: {"text": "hello"}\n\n
          When finished, we send:  data: [DONE]\n\n
          The double newline (\n\n) tells the browser "this event is complete".

        Input:  {"messages": [{"role": "user", "content": "..."}, ...]}
        Output: a stream of SSE events (not a JSON blob)
        """
        # Tell the browser: keep this connection open, we'll send events over time
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        try:
            # .stream() is like .create() but yields text as it's generated
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=body["messages"],
            ) as stream:
                for text in stream.text_stream:
                    # Wrap the chunk in JSON and format as an SSE event
                    chunk = json.dumps({"text": text})
                    self.wfile.write(f"data: {chunk}\n\n".encode("utf-8"))
                    self.wfile.flush()   # Send immediately — don't buffer in memory

            # Signal to the browser that the stream is finished
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

        except Exception as e:
            # Print to terminal so you can see what went wrong
            print(f"\n  [STREAM ERROR] {e}\n")
            # Also send an error event to the browser
            error = json.dumps({"error": str(e)})
            self.wfile.write(f"data: {error}\n\n".encode("utf-8"))
            self.wfile.flush()

    # ── Route: Start Assumption Negotiation ───────────────────────────────────
    def _handle_initial(self, client, body):
        """
        Start the assumption workflow: get a recommendation + 5 assumptions.

        Input:  {"query": "Should I buy oat milk or regular milk?"}
        Output: {"recommendation": "...", "assumptions": {"A1": "...", ...}}
        """
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="""
                You are an assistant that provides recommendations based on user queries.
                For each recommendation, provide 5 key assumptions you made.
                IMPORTANT:
                  - State assumptions in POSITIVE form (avoid double negatives)
                  - Make assumptions clear and easy to confirm with yes/no

                Return ONLY valid raw JSON. No markdown, no code blocks:
                {
                    "recommendation": "X",
                    "assumptions": {
                        "A1": "Assumption 1...",
                        "A2": "Assumption 2..."
                    }
                }
            """,
            messages=[{"role": "user", "content": body["query"]}],
        )
        return json.loads(response.content[0].text)

    # ── Route: Generate Revised Recommendation ────────────────────────────────
    def _handle_revise(self, client, body):
        """
        Generate a revised recommendation based on accepted assumptions.

        Input:  {
                    "initial_response": {"recommendation": "...", "assumptions": {...}},
                    "feedback": {"selected_responses": {"A1": 1, "A2": 0, ...},
                                 "new_assumptions": {"A6": "I have a nut allergy"}}
                }
        Output: {"recommendation": "...", "assumptions": {...}}
        """
        initial = body["initial_response"]
        feedback = body["feedback"]

        # Filter to only the accepted assumptions (value = 1) + any new ones
        accepted = {}
        for key, value in feedback["selected_responses"].items():
            if value == 1:
                accepted[key] = initial["assumptions"][key]
        accepted.update(feedback.get("new_assumptions", {}))

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="""
                You are an assistant helping a user refine their decision through assumption negotiation.
                Generate a revised recommendation that BALANCES ALL accepted assumptions.
                - Do NOT let any single factor dominate the decision
                - Consider trade-offs between conflicting factors

                Return ONLY valid raw JSON. No markdown, no code blocks:
                {
                    "recommendation": "X",
                    "assumptions": {"A1": "...", "A2": "..."}
                }
            """,
            messages=[{
                "role": "user",
                "content": (
                    f"INITIAL RECOMMENDATION: {initial['recommendation']}\n\n"
                    f"ACCEPTED ASSUMPTIONS:\n{json.dumps(accepted, indent=2)}\n\n"
                    "Generate a revised recommendation balancing ALL these assumptions."
                ),
            }],
        )
        return json.loads(response.content[0].text)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _send_json(self, data):
        """Send a JSON response back to the browser."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # With HTTP/1.1, tell the browser this connection is done after this response
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code, message):
        """Send an error response."""
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        """Override default logging to show cleaner request messages."""
        print(f"  {self.address_string()} → {fmt % args}")


# ─── Start the Server ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    PORT = 5001
    # ThreadingHTTPServer handles one request at a time across threads,
    # which prevents the server from freezing while waiting for Claude's response.
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(("127.0.0.1", PORT), ChatHandler)

    print(f"\n  Claude is running at:  http://localhost:{PORT}")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
