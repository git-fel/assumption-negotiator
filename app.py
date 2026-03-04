"""
Claude — ChatGPT-style UI with two modes
=========================================
A single Streamlit app styled to look like ChatGPT, with two selectable modes:

  💬 Chat                  — regular back-and-forth conversation with Claude
  🧠 Assumption Negotiator — the full assumption negotiation workflow

HOW THE MODE SWITCHING WORKS:
  At the top of the page there are two pill buttons (like ChatGPT's
  "Search / Reason / Canvas" buttons). Clicking one switches modes
  and resets the conversation automatically.

HOW STREAMLIT STATE WORKS (important for understanding this file):
  Streamlit reruns the entire script every time the user interacts.
  We use `st.session_state` (a dictionary that persists between reruns)
  to remember things like chat history, which phase we're in, etc.
  Every `st.rerun()` call forces the script to restart from the top.

Run with:
    streamlit run app.py

Requires Streamlit >= 1.39 (for st.pills support).
"""

import streamlit as st
import json
import os
from anthropic import Anthropic

# ─── Connect to the Anthropic API ─────────────────────────────────────────────
# Reads your ANTHROPIC_API_KEY from environment variables, same as main.py.
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ─── Page Configuration ────────────────────────────────────────────────────────
# Must be the very first Streamlit call in the script.
st.set_page_config(
    page_title="Claude",
    page_icon="✦",
    layout="centered",              # Keeps content centered, like ChatGPT
    initial_sidebar_state="collapsed",
)


# ─── CSS: ChatGPT Dark Theme ───────────────────────────────────────────────────
# We inject custom CSS to override Streamlit's default white theme.
# ChatGPT's dark mode uses:
#   #212121 — main background (very dark gray)
#   #171717 — sidebar background (even darker)
#   #2f2f2f — cards, input area, buttons (slightly lighter gray)
#   #3f3f3f — borders and dividers
#   #ececec — primary text (off-white)
#   #8e8ea0 — secondary/placeholder text (muted)
st.markdown("""
<style>

/* ── Hide default Streamlit branding ─────────────────────────────────────── */
#MainMenu, footer, header    { visibility: hidden; }
[data-testid="stDecoration"],
[data-testid="stToolbar"]    { display: none; }

/* ── Main background ──────────────────────────────────────────────────────── */
.stApp {
    background-color: #212121 !important;
}

/* ── Center content and match ChatGPT's max width ────────────────────────── */
.main .block-container {
    max-width: 48rem !important;
    padding-top: 1rem !important;
    padding-bottom: 0 !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #171717 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {
    color: #ececec !important;
}

/* ── All regular text ─────────────────────────────────────────────────────── */
p, span, label, li, .stMarkdown {
    color: #ececec !important;
}
h1, h2, h3, h4, h5 {
    color: #ececec !important;
}

/* ── Chat messages: transparent background (no bubble on the left) ────────── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.75rem 0 !important;
}
[data-testid="stChatMessageContent"] p {
    color: #ececec !important;
}

/* ── Chat input bar at the bottom ─────────────────────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottom"] > div {
    background-color: #212121 !important;
}
[data-testid="stChatInputContainer"] {
    background-color: #2f2f2f !important;
    border-radius: 1rem !important;
    border: 1px solid #3f3f3f !important;
}
[data-testid="stChatInput"] textarea {
    background-color: transparent !important;
    color: #ececec !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #8e8ea0 !important;
}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
    background-color: #2f2f2f !important;
    color: #ececec !important;
    border: 1px solid #3f3f3f !important;
    border-radius: 0.5rem !important;
    transition: background 0.15s ease;
}
.stButton > button:hover {
    background-color: #3a3a3a !important;
}

/* ── Mode selector pills ──────────────────────────────────────────────────── */
/* This is the equivalent of ChatGPT's "Search / Reason / Canvas" pills */
[data-testid="stPills"] {
    margin-bottom: 0.25rem;
}
[data-testid="stPills"] button {
    background-color: transparent !important;
    color: #8e8ea0 !important;
    border: 1px solid #3f3f3f !important;
    border-radius: 999px !important;    /* fully rounded — pill shape */
    font-size: 0.82rem !important;
    padding: 0.25rem 0.85rem !important;
}
[data-testid="stPills"] button[aria-checked="true"] {
    background-color: #2f2f2f !important;
    color: #ececec !important;
    border-color: #6b6b6b !important;
}

/* ── Assumption cards (bordered containers) ───────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #2f2f2f !important;
    border: 1px solid #3f3f3f !important;
    border-radius: 0.75rem !important;
}

/* ── Text input (for the "new factor" field) ──────────────────────────────── */
.stTextInput > div > div > input {
    background-color: #2f2f2f !important;
    color: #ececec !important;
    border: 1px solid #3f3f3f !important;
    border-radius: 0.5rem !important;
}

/* ── Alert / info / success / warning / error boxes ──────────────────────── */
[data-testid="stAlert"] {
    background-color: #2f2f2f !important;
    border-radius: 0.5rem !important;
    color: #ececec !important;
}

/* ── Horizontal divider line ──────────────────────────────────────────────── */
hr {
    border-color: #3f3f3f !important;
}

/* ── Loading spinner ──────────────────────────────────────────────────────── */
.stSpinner > div {
    border-top-color: #ececec !important;
}

/* ── Caption / secondary text ─────────────────────────────────────────────── */
.stCaption,
[data-testid="stCaptionContainer"] {
    color: #8e8ea0 !important;
}

</style>
""", unsafe_allow_html=True)


# ─── Helper: Fresh State ───────────────────────────────────────────────────────
# Returns a clean dictionary of all session variables.
# We use a function (not a plain dict) because Python dicts are mutable —
# reusing the same dict object for resets would cause subtle memory bugs.
def fresh_state():
    return {
        # Which mode the user has selected
        "mode": "💬 Chat",

        # Chat history: list of {"role": "user"/"assistant", "content": "..."}
        "messages": [],

        # Current phase within Assumption Negotiator mode
        "phase": "query",

        # The first API result: {"recommendation": "...", "assumptions": {...}}
        "initial_response": None,

        # What the user said about each assumption
        "feedback": {
            "selected_responses": {},  # {"A1": 1, "A2": 0, ...}  1=yes, 0=no
            "new_assumptions": {},     # {"A6": "user's new consideration"}
        },

        # Whether the "type your new factor" text box is visible
        "adding_factor": False,

        # Internal counter used to reset the st.pills widget on "New Chat".
        # Changing the key forces Streamlit to treat it as a brand-new widget.
        "_pills_version": 0,
    }


# ─── Initialize Session State ─────────────────────────────────────────────────
# On the very first run, populate session state from fresh_state().
# On all subsequent reruns, this is skipped — existing values are preserved.
for key, val in fresh_state().items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── API Function: Regular Chat ───────────────────────────────────────────────
def chat_with_claude(messages):
    """
    Send the full conversation history to Claude and return its reply.
    Passing all previous messages lets Claude remember what was said earlier.
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=messages,
    )
    return response.content[0].text


# ─── API Function: Generate Initial Recommendation ────────────────────────────
def generate_initial_response(user_input):
    """
    Assumption Negotiator mode, Phase 1:
    Ask Claude for a recommendation and the 5 assumptions behind it.
    Returns a dict: {"recommendation": "...", "assumptions": {"A1": ..., ...}}
    """
    response = client.messages.create(
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
    return json.loads(response.content[0].text)


# ─── API Function: Generate Revised Recommendation ────────────────────────────
def generate_revised_response(initial_response, feedback):
    """
    Assumption Negotiator mode, Phase 4:
    Send accepted assumptions (+ any new ones) to Claude for a revised recommendation.
    Returns a dict: {"recommendation": "...", "assumptions": {...}}
    """
    llm_input = {
        "old_recommendation": initial_response["recommendation"],
        "assumptions": {},
    }

    # Only include assumptions the user accepted (value = 1)
    for key, value in feedback["selected_responses"].items():
        if value == 1:
            llm_input["assumptions"][key] = initial_response["assumptions"][key]

    # Add any new factors the user introduced
    llm_input["assumptions"].update(feedback["new_assumptions"])

    api_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system="""
            You are an assistant helping a user refine their decision through assumption negotiation.

            YOUR TASK:
            Generate a revised recommendation that BALANCES ALL the accepted assumptions AND new considerations.
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
                INITIAL RECOMMENDATION: {llm_input["old_recommendation"]}

                ACCEPTED ASSUMPTIONS (user confirmed these are correct):
                {json.dumps(llm_input["assumptions"], indent=2)}

                Generate a revised recommendation balancing ALL these assumptions.
                No single factor should dominate — consider the trade-offs.
            """,
        }],
    )
    return json.loads(api_response.content[0].text)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ✦ Claude")

    # "New Chat" button — resets everything, including the mode pills
    if st.button("✏️  New chat", use_container_width=True):
        new = fresh_state()
        # Incrementing _pills_version changes the key of st.pills, which forces
        # it to re-render as a new widget with the default value ("💬 Chat")
        new["_pills_version"] = st.session_state._pills_version + 1
        for key, val in new.items():
            st.session_state[key] = val
        st.rerun()

    st.markdown("---")
    st.markdown(f"**Current mode**")
    st.markdown(f"`{st.session_state.mode}`")
    st.markdown("---")
    st.caption("Powered by Claude (Anthropic)")


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## ✦ Claude")


# ─────────────────────────────────────────────────────────────────────────────
# MODE SELECTOR PILLS
# This is the equivalent of ChatGPT's "Search / Reason / Canvas" pills.
# Clicking a pill switches modes and resets the conversation.
# ─────────────────────────────────────────────────────────────────────────────
# The `key` includes _pills_version so that clicking "New Chat" forces a
# fresh widget render (resetting the selected pill back to the default).
selected_mode = st.pills(
    label="Mode",
    options=["💬 Chat", "🧠 Assumption Negotiator"],
    default=st.session_state.mode,
    label_visibility="collapsed",
    key=f"pills_{st.session_state._pills_version}",
)

# Detect when the user clicked a different mode → reset the conversation
if selected_mode and selected_mode != st.session_state.mode:
    new = fresh_state()
    new["mode"] = selected_mode
    new["_pills_version"] = st.session_state._pills_version  # keep the same pills key
    for key, val in new.items():
        st.session_state[key] = val
    st.rerun()

# Keep session_state.mode in sync with the pill selection
if selected_mode:
    st.session_state.mode = selected_mode

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER CHAT HISTORY
# This always runs on every rerun — it draws all stored messages.
# ─────────────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):   # "user" → person icon, "assistant" → robot icon
        st.markdown(msg["content"])


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — CHAT
# Regular conversation: user types → Claude responds → repeat.
# The full message history is sent on each turn so Claude remembers context.
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.mode == "💬 Chat":

    user_input = st.chat_input("Message Claude...")

    if user_input:
        # Store user message and display it immediately
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Call Claude with the full conversation history
        with st.spinner(""):
            reply = chat_with_claude(st.session_state.messages)

        # Store and display Claude's response
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — ASSUMPTION NEGOTIATOR
# A multi-phase workflow:
#   query → assumption_review → new_consideration → generating_revised → done
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.mode == "🧠 Assumption Negotiator":

    # ── Phase 1: QUERY ────────────────────────────────────────────────────────
    # User types their question. We call the API and move to assumption review.
    if st.session_state.phase == "query":

        user_input = st.chat_input("Enter your query, e.g. 'Should I buy oat milk or regular milk?'")

        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})

            with st.spinner("Generating recommendation..."):
                initial = generate_initial_response(user_input)

            st.session_state.initial_response = initial

            # Add the initial recommendation as an assistant message in the chat
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    f"**My initial recommendation:** {initial['recommendation']}\n\n"
                    "---\n\n"
                    "I made some assumptions to reach this recommendation. "
                    "Please review each one below and tell me if it applies to you."
                ),
            })

            st.session_state.phase = "assumption_review"
            st.rerun()

    # ── Phase 2: ASSUMPTION REVIEW ────────────────────────────────────────────
    # Each assumption is shown as a bordered card with Yes/No buttons.
    # Once all are answered, the app automatically moves to the next phase.
    elif st.session_state.phase == "assumption_review":

        assumptions = st.session_state.initial_response["assumptions"]
        answered = st.session_state.feedback["selected_responses"]

        st.markdown("### Review the Assumptions")
        st.markdown("Click **Yes** if the assumption applies to you, or **No** if it doesn't:")

        all_answered = True   # Flip to False if any assumption is still unanswered

        for key, text in assumptions.items():
            with st.container(border=True):
                st.markdown(f"**{key}:** {text}")

                if key in answered:
                    # Already answered — show locked-in result
                    if answered[key] == 1:
                        st.success("✅ You accepted this assumption")
                    else:
                        st.error("❌ You rejected this assumption")
                else:
                    # Not yet answered — show Yes/No buttons
                    all_answered = False
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Yes, this applies", key=f"yes_{key}"):
                            st.session_state.feedback["selected_responses"][key] = 1
                            st.rerun()
                    with col2:
                        if st.button("❌ No, this doesn't apply", key=f"no_{key}"):
                            st.session_state.feedback["selected_responses"][key] = 0
                            st.rerun()

        # All 5 answered → move forward automatically
        if all_answered:
            st.session_state.phase = "new_consideration"
            st.rerun()

    # ── Phase 3: NEW CONSIDERATION ────────────────────────────────────────────
    # Ask if the user wants to add something the AI didn't consider.
    elif st.session_state.phase == "new_consideration":

        st.markdown("### Add a New Factor?")
        st.markdown("Is there anything you'd like me to consider that wasn't covered above?")

        if not st.session_state.adding_factor:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, add a factor"):
                    st.session_state.adding_factor = True
                    st.rerun()
            with col2:
                if st.button("❌ No, proceed"):
                    st.session_state.phase = "generating_revised"
                    st.rerun()

        else:
            # User said yes → show a text input field
            new_factor = st.text_input(
                "Describe the new factor:",
                placeholder="e.g. I have a nut allergy",
            )
            if st.button("Submit and generate revised recommendation"):
                if new_factor.strip():
                    # Create a new assumption ID (e.g. "A6" if there were 5)
                    new_id = "A" + str(len(st.session_state.initial_response["assumptions"]) + 1)
                    st.session_state.feedback["new_assumptions"] = {new_id: new_factor.strip()}
                    st.session_state.phase = "generating_revised"
                    st.rerun()
                else:
                    st.warning("Please enter a factor before submitting.")

    # ── Phase 4: GENERATING REVISED ───────────────────────────────────────────
    # Call the API and add the revised recommendation to the chat history.
    elif st.session_state.phase == "generating_revised":

        with st.spinner("Generating revised recommendation..."):
            revised = generate_revised_response(
                st.session_state.initial_response,
                st.session_state.feedback,
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"**Revised Recommendation:** {revised['recommendation']}",
        })

        st.session_state.phase = "done"
        st.rerun()

    # ── Phase 5: DONE ─────────────────────────────────────────────────────────
    # Show a success message and let the user start a new query.
    elif st.session_state.phase == "done":

        st.success("✅ Recommendation complete!")

        if st.button("🔄 Start a new query"):
            new = fresh_state()
            new["mode"] = "🧠 Assumption Negotiator"
            new["_pills_version"] = st.session_state._pills_version
            for key, val in new.items():
                st.session_state[key] = val
            st.rerun()
