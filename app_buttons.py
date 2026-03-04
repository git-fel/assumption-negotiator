"""
Assumption Negotiator — Button UI
==================================
A Streamlit web interface that looks like a chat app (similar to ChatGPT).
Assumptions are shown as interactive cards with clickable Yes/No buttons.

HOW THIS FILE WORKS:
- Streamlit reruns the entire script every time the user clicks something.
- We use `st.session_state` to remember values between reruns (like chat history).
- The app moves through "phases" — like stages of a conversation:
    1. "query"              → User types their question
    2. "assumption_review"  → User clicks Yes/No on each assumption card
    3. "new_consideration"  → User says if they want to add a new factor
    4. "generating_revised" → App calls the API and gets a revised recommendation
    5. "done"               → Final recommendation shown

Run with:
    streamlit run app_buttons.py
"""

import streamlit as st
import json
import os
from anthropic import Anthropic

# ─── Connect to the Anthropic API ─────────────────────────────────────────────
# Same as main.py: reads your ANTHROPIC_API_KEY environment variable.
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ─── Page Setup ────────────────────────────────────────────────────────────────
# This must be the first Streamlit call in the script.
st.set_page_config(
    page_title="Assumption Negotiator",
    page_icon="🧠",
    layout="centered",   # Keeps content in the middle of the screen, like ChatGPT
)

st.title("🧠 Assumption Negotiator")
st.caption("An AI assistant that shows its reasoning and asks you to validate it.")


# ─── Helper: Get Fresh Default State ──────────────────────────────────────────
# We use a function (not a plain dict) because Python dicts are mutable.
# If we stored a dict directly and reused it for resets, all resets would
# share the same object in memory — causing hard-to-debug bugs.
def fresh_state():
    return {
        # Chat history: a list of {"role": "user"/"assistant", "content": "..."}
        "messages": [],

        # Which step we're on. Moves forward as the user completes each phase.
        "phase": "query",

        # The first API response: {"recommendation": "...", "assumptions": {...}}
        "initial_response": None,

        # What the user said about each assumption
        "feedback": {
            "selected_responses": {},  # e.g. {"A1": 1, "A2": 0, "A3": 1}  (1=yes, 0=no)
            "new_assumptions": {},     # e.g. {"A6": "I have a nut allergy"}
        },

        # The final revised API response
        "revised_response": None,

        # Controls whether the "add a new factor" text input is visible
        "adding_factor": False,
    }


# ─── Initialize Session State ─────────────────────────────────────────────────
# On the very first run, create all state variables from fresh_state().
# On subsequent reruns, this block is skipped because the keys already exist.
for key, val in fresh_state().items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── API Function: Generate Initial Recommendation ────────────────────────────
# Identical logic to main.py — sends user query, gets back recommendation + assumptions.
def generate_initial_response(user_input):
    """Call Claude API and return a dict with 'recommendation' and 'assumptions'."""
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

            The return format should only be in valid raw JSON without any markdown formatting, code blocks, or
            additional text. Do NOT use ```json or ``` markers. The JSON should follow this exact structure:
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
# Same logic as main.py — filters to accepted assumptions, adds new ones, asks for revision.
def generate_revised_response(initial_response, feedback):
    """Call Claude API and return a revised recommendation based on accepted assumptions."""
    llm_input_data = {
        "old_recommendation": initial_response["recommendation"],
        "assumptions": {},
    }

    # Only pass assumptions the user accepted (value = 1)
    for key, value in feedback["selected_responses"].items():
        if value == 1:
            llm_input_data["assumptions"][key] = initial_response["assumptions"][key]

    # Add any new factors the user provided
    llm_input_data["assumptions"].update(feedback["new_assumptions"])

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
            - Explain how you're balancing multiple factors if they conflict

            The return format should only be in valid raw JSON without any markdown formatting, code blocks, or additional text.
            Do NOT use ```json or ``` markers. The JSON should follow this exact structure:
            {
                "recommendation": "X",
                "assumptions": {
                    "A1": "Assumption 1 details...",
                    "A2": "Assumption 2 details..."
                }
            }
        """,
        messages=[
            {
                "role": "user",
                "content": f"""
                    INITIAL RECOMMENDATION:
                        {llm_input_data["old_recommendation"]}

                    ACCEPTED ASSUMPTIONS (user confirmed these are correct):
                        {json.dumps(llm_input_data["assumptions"], indent=2)}

                    Please generate a REVISED recommendation that balances ALL these accepted assumptions.
                    No single factor should dominate - consider the trade-offs.
                """,
            }
        ],
    )
    return json.loads(api_response.content[0].text)


# ─────────────────────────────────────────────────────────────────────────────
# RENDER CHAT HISTORY
# This block always runs first on every rerun.
# It draws all messages stored in st.session_state.messages.
# ─────────────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):   # "user" → person icon, "assistant" → robot icon
        st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — QUERY
# Show a chat input box. When the user types and submits, call the API.
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.phase == "query":

    user_input = st.chat_input("Enter your query, e.g. 'Should I buy oat milk or regular milk?'")

    if user_input:
        # Add the user's message to chat history (so it appears in the chat)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Call the API while showing a loading spinner
        with st.spinner("Generating recommendation..."):
            initial = generate_initial_response(user_input)

        st.session_state.initial_response = initial

        # Add the initial recommendation as an assistant chat message
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"**My initial recommendation:** {initial['recommendation']}\n\n"
                "---\n\n"
                "I made some assumptions to reach this recommendation. "
                "Please review each one below and tell me if it applies to you."
            ),
        })

        # Move to the next phase and redraw the page
        st.session_state.phase = "assumption_review"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — ASSUMPTION REVIEW
# Show all 5 assumptions as bordered cards with Yes/No buttons.
# Answered assumptions lock in and show a green/red result.
# When all 5 are answered, the app automatically moves forward.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "assumption_review":

    assumptions = st.session_state.initial_response["assumptions"]
    answered = st.session_state.feedback["selected_responses"]

    st.markdown("### Review the Assumptions")
    st.markdown("Click **Yes** if the assumption applies to you, or **No** if it doesn't:")

    all_answered = True  # Will flip to False if any assumption is still unanswered

    for key, text in assumptions.items():
        with st.container(border=True):
            st.markdown(f"**{key}:** {text}")

            if key in answered:
                # Already answered — show a locked-in result (no buttons)
                if answered[key] == 1:
                    st.success("✅ You accepted this assumption")
                else:
                    st.error("❌ You rejected this assumption")
            else:
                # Not yet answered — show Yes/No buttons side by side
                all_answered = False
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, this applies to me", key=f"yes_{key}"):
                        st.session_state.feedback["selected_responses"][key] = 1
                        st.rerun()
                with col2:
                    if st.button("❌ No, this doesn't apply", key=f"no_{key}"):
                        st.session_state.feedback["selected_responses"][key] = 0
                        st.rerun()

    # Once every assumption has a Yes/No answer, automatically move forward
    if all_answered:
        st.session_state.phase = "new_consideration"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — NEW CONSIDERATION
# Ask if the user wants to add a factor the AI didn't think of.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "new_consideration":

    st.markdown("### Add a New Factor?")
    st.markdown(
        "Is there anything you'd like me to consider that wasn't covered "
        "in the assumptions above?"
    )

    if not st.session_state.adding_factor:
        # Show Yes/No choice buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, I want to add a factor"):
                st.session_state.adding_factor = True
                st.rerun()
        with col2:
            if st.button("❌ No, proceed to revised recommendation"):
                st.session_state.phase = "generating_revised"
                st.rerun()

    else:
        # User said Yes — show a text input for them to type the new factor
        new_factor = st.text_input(
            "Describe the new factor:",
            placeholder="e.g. I have a nut allergy",
        )
        if st.button("Submit and generate revised recommendation"):
            if new_factor.strip():
                # Assign a unique ID (e.g. "A6" if there were 5 original assumptions)
                new_id = "A" + str(len(st.session_state.initial_response["assumptions"]) + 1)
                st.session_state.feedback["new_assumptions"] = {new_id: new_factor.strip()}
                st.session_state.phase = "generating_revised"
                st.rerun()
            else:
                st.warning("Please enter a factor before submitting.")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — GENERATING REVISED RECOMMENDATION
# Call the API for the revised recommendation, then add it to chat history.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "generating_revised":

    with st.spinner("Generating revised recommendation..."):
        revised = generate_revised_response(
            st.session_state.initial_response,
            st.session_state.feedback,
        )
        st.session_state.revised_response = revised

    # Add revised recommendation to the chat history
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"**Revised Recommendation:** {revised['recommendation']}",
    })

    st.session_state.phase = "done"
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — DONE
# Show a success banner and a "Start over" button.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "done":

    st.success("✅ Recommendation complete! You can start a new query below.")

    if st.button("🔄 Start a new query"):
        # Reset all state back to fresh defaults
        for key, val in fresh_state().items():
            st.session_state[key] = val
        st.rerun()
