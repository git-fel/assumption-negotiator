"""
Assumption Negotiator — Chat UI (Text-based)
=============================================
A Streamlit web interface where everything happens through the chat box.
The AI asks one assumption at a time, and you type 'yes' or 'no' to respond.

HOW THIS DIFFERS FROM app_buttons.py:
- No special assumption cards or buttons
- The AI asks assumptions one at a time as chat messages
- You type 'yes' or 'no' in the chat input box — just like a real conversation
- Everything stays inside the chat thread

HOW THE PHASES WORK:
    1. "query"              → User types their question in the chat box
    2. "asking_assumption"  → AI asks each assumption one at a time; user types yes/no
    3. "asking_new_factor"  → AI asks if user wants to add a new factor; user types yes/no
    4. "typing_new_factor"  → User types their new factor as a chat message
    5. "generating_revised" → App calls the API and gets a revised recommendation
    6. "done"               → Final recommendation shown

Run with:
    streamlit run app_chat.py
"""

import streamlit as st
import json
import os
from anthropic import Anthropic

# ─── Connect to the Anthropic API ─────────────────────────────────────────────
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ─── Page Setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Assumption Negotiator",
    page_icon="🧠",
    layout="centered",
)

st.title("🧠 Assumption Negotiator")
st.caption("An AI assistant that surfaces its reasoning through conversation.")


# ─── Helper: Get Fresh Default State ──────────────────────────────────────────
def fresh_state():
    return {
        # Chat history — starts with a greeting message from the assistant
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "Hello! I'm the Assumption Negotiator.\n\n"
                    "Tell me what decision you're facing and I'll give you a recommendation "
                    "along with the assumptions I made. You can then tell me which ones are "
                    "correct for your situation, and I'll revise my recommendation accordingly."
                ),
            }
        ],

        # Which step of the workflow we're on
        "phase": "query",

        # The first API response: {"recommendation": "...", "assumptions": {...}}
        "initial_response": None,

        # What the user said about each assumption
        "feedback": {
            "selected_responses": {},  # e.g. {"A1": 1, "A2": 0}  (1=yes, 0=no)
            "new_assumptions": {},     # e.g. {"A6": "I have a nut allergy"}
        },

        # Index into the assumptions dict — tracks which assumption we're currently asking
        "current_assumption_idx": 0,
    }


# ─── Initialize Session State ─────────────────────────────────────────────────
for key, val in fresh_state().items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── API Function: Generate Initial Recommendation ────────────────────────────
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
# Always runs first. Draws every message in st.session_state.messages.
# ─────────────────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — QUERY
# User types their question. The app calls the API and asks the first assumption.
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.phase == "query":

    user_input = st.chat_input("Type your question or decision here...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Call the API while showing a spinner
        with st.spinner("Thinking..."):
            initial = generate_initial_response(user_input)

        st.session_state.initial_response = initial

        # Show the initial recommendation as an assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"**My initial recommendation:** {initial['recommendation']}\n\n"
                "---\n\n"
                "Now let me walk you through the assumptions I made. "
                "For each one, reply **yes** if it's correct for you, or **no** if it isn't."
            ),
        })

        # Immediately ask the first assumption
        assumption_keys = list(initial["assumptions"].keys())
        first_key = assumption_keys[0]
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"**{first_key}:** {initial['assumptions'][first_key]}\n\n"
                "Is this correct? *(yes / no)*"
            ),
        })

        st.session_state.current_assumption_idx = 0
        st.session_state.phase = "asking_assumption"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — ASKING ASSUMPTIONS ONE BY ONE
# User types 'yes' or 'no' for each assumption.
# The app records the answer and then asks the next assumption.
# When all assumptions are answered, it moves to the next phase.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "asking_assumption":

    user_input = st.chat_input("Type 'yes' or 'no'...")

    if user_input:
        user_text = user_input.strip().lower()
        st.session_state.messages.append({"role": "user", "content": user_input})

        if user_text not in ["yes", "no"]:
            # Invalid response — ask again without moving forward
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Please type **yes** or **no** to respond to the assumption above.",
            })
            st.rerun()

        else:
            # Valid response — record it and move to the next assumption
            assumptions = st.session_state.initial_response["assumptions"]
            assumption_keys = list(assumptions.keys())
            current_idx = st.session_state.current_assumption_idx
            current_key = assumption_keys[current_idx]

            # Store: 1 for yes, 0 for no
            st.session_state.feedback["selected_responses"][current_key] = (
                1 if user_text == "yes" else 0
            )

            next_idx = current_idx + 1

            if next_idx < len(assumption_keys):
                # Ask the next assumption
                next_key = assumption_keys[next_idx]
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": (
                        f"**{next_key}:** {assumptions[next_key]}\n\n"
                        "Is this correct? *(yes / no)*"
                    ),
                })
                st.session_state.current_assumption_idx = next_idx

            else:
                # All assumptions answered — ask about adding a new factor
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": (
                        "Great, you've reviewed all the assumptions!\n\n"
                        "Is there any other factor you'd like me to consider "
                        "that wasn't in my assumptions? *(yes / no)*"
                    ),
                })
                st.session_state.phase = "asking_new_factor"

            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — ASKING ABOUT A NEW CONSIDERATION
# User types yes or no to whether they want to add something new.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "asking_new_factor":

    user_input = st.chat_input("Type 'yes' or 'no'...")

    if user_input:
        user_text = user_input.strip().lower()
        st.session_state.messages.append({"role": "user", "content": user_input})

        if user_text == "yes":
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Sure! Please describe the new factor you'd like me to consider:",
            })
            st.session_state.phase = "typing_new_factor"

        elif user_text == "no":
            # Skip directly to generating the revised recommendation
            st.session_state.phase = "generating_revised"

        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Please type **yes** or **no**.",
            })

        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — USER TYPES THE NEW FACTOR
# Whatever the user types here is treated as their new consideration.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "typing_new_factor":

    user_input = st.chat_input("Describe the new factor...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Assign a unique ID (e.g. "A6" if there were 5 original assumptions)
        new_id = "A" + str(len(st.session_state.initial_response["assumptions"]) + 1)
        st.session_state.feedback["new_assumptions"] = {new_id: user_input.strip()}

        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"Got it — I'll factor in: *{user_input.strip()}*\n\n"
                "Generating your revised recommendation now..."
            ),
        })

        st.session_state.phase = "generating_revised"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — GENERATE REVISED RECOMMENDATION
# Call the API one more time with the accepted assumptions + any new factor.
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 — DONE
# Show a success banner and a "Start over" button.
# ─────────────────────────────────────────────────────────────────────────────
elif st.session_state.phase == "done":

    st.success("✅ Done! You can start a new conversation below.")

    if st.button("🔄 Start a new conversation"):
        for key, val in fresh_state().items():
            st.session_state[key] = val
        st.rerun()
