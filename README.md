# Assumption Negotiation Assistant
A human-in-the-loop AI system that helps people make better decisions by explicitly negotiating the assumptions behind recommendations.

---

## Table of Contents
- [About This Project](#about-this-project)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Design Decisions & Challenges](#design-decisions--challenges)
- [Ideal Applications](#ideal-applications)
- [Future Enhancements](#future-enhancements)
- [Technical Documentation](#technical-documentation)
- [Development Notes](#development-notes)
- [Final Thoughts](#final-thoughts)
- [License](#license)

---

## About This Project

### Technical Problem Statement

Build a human-in-the-loop (HITL) generative AI system where human feedback explicitly changes system behavior across iterations. The system should show how GenAI can shape user behavior, e.g., decision-making, learning, or habit formation.

### Approach: Why Assumption Negotiation?

Most AI systems work like this: you ask a question, you get an answer. Simple, but not particularly useful for complex decisions where there's real uncertainty.

I wanted to try something different. Instead of just giving recommendations, this system **surfaces its reasoning** and asks you to validate or challenge it. The key idea: decision-making isn't about passively receiving answers. It's about actively engaging with the reasoning process.

**Here's what makes this interesting:**

The system doesn't position itself as the expert with all the answers. Instead, it says "Here's what I'm recommending, and here are the assumptions I'm making. Are these assumptions actually true for you?"

This does a few things:
- **Shifts the dynamic** from "AI gives answers" to "AI helps you think"
- **Forces critical thinking** by making you consider what you're willing to accept as true
- **Reduces blind trust** by making recommendations conditional on explicit assumptions
- **Keeps humans accountable** for value judgments while the AI handles the logical reasoning

**How it shapes behavior:** People who use this learn to question recommendations (from AI or otherwise), articulate their real priorities, and think through tradeoffs. Those are skills that stick with you beyond this specific tool.

---

## Quick Start

### What You'll Need
- Python 3.7 or higher
- An Anthropic API key ([grab one here](https://console.anthropic.com/))

### Getting It Running

**1. Go to project folder**
```
cd /path/to/your/project
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**4. Set up your API key**

Add this to your `~/.zshrc` (or `~/.bashrc` if you're using bash):
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Save and reload:
```bash
source ~/.zshrc
```

**5. Run it**
```bash
python main.py
```

### What It Looks Like

```
PLEASE ENTER YOUR QUERY: Should I buy oat milk or regular milk for my coffee?

INITIAL RECOMMENDATION: I recommend oat milk for your coffee, as it provides excellent texture...

THIS RECOMMENDATION IS BASED ON THE FOLLOWING ASSUMPTIONS. PLEASE REVIEW THEM:

A1: You don't have lactose intolerance or dairy allergies as a primary concern
IS THIS ASSUMPTION CORRECT? (yes/no):

A2: You care about environmental impact and sustainability in your purchasing decisions
IS THIS ASSUMPTION CORRECT? (yes/no):

...

DO YOU WANT THE SYSTEM TO CONSIDER ANY NEW FACTOR? (yes/no): yes
PLEASE ENTER THE NEW CONSIDERATION: I have a nut allergy

REVISED RECOMMENDATION: Oat milk remains the best choice given your nut allergy...
```

---

## How It Works

The system runs through three phases:

### Phase 1: Initial Recommendation
1. You enter a query (like "What should I do about X?")
2. Claude generates a recommendation plus 5 key assumptions stated in positive form
3. You see the recommendation

### Phase 2: Assumption Negotiation (The HITL Part)
1. The system shows you each assumption
2. You accept or reject each one
3. You can add new factors the AI didn't consider
4. Everything gets structured into clean feedback

### Phase 3: Revised Recommendation
1. System filters out rejected assumptions
2. Adds your new considerations
3. Claude generates a revised recommendation that balances ALL the validated assumptions
4. You see the updated recommendation

### The Data Flow

```
User Query
    ↓
[Claude: Generate recommendation + assumptions]
    ↓
Display recommendation
    ↓
[Human: Accept/reject assumptions + add new ones]
    ↓
Filter to accepted assumptions only
    ↓
[Claude: Generate revised recommendation that balances everything]
    ↓
Display revised recommendation
```

---

## Design Decisions & Challenges

### 1. Phrasing Assumptions in Positive Form

**The Problem:** I initially let Claude phrase assumptions however it wanted, and I quickly realized double negatives were confusing. When you see "You don't have lactose intolerance," your brain has to do extra work to figure out if that's true or false.

**What I Changed:** I updated the system prompt to require positive phrasing:
- ✅ "You can consume dairy products without issues"
- ❌ "You don't have lactose intolerance"

**Result:** Way easier to confirm yes/no without mental gymnastics or errors in selection.

---

### 2. Making Sure All Assumptions Get Fair Weight

**The Problem:** In my initial version, if you accepted 4 assumptions favoring one option and then added a single new consideration, the revised recommendation would completely flip based on that one new factor.

For example: You accept 4 assumptions all pointing to oat milk, then add "I prefer the taste of regular milk." The system would recommend regular milk, ignoring everything else you'd validated.

**What I Changed:** I rewrote the system prompt for `generate_revised_response()` to explicitly instruct:
- "Generate a revised recommendation that BALANCES ALL the accepted assumptions"
- "Do NOT let any single factor dominate the decision"
- "Consider trade-offs between conflicting factors"

**Result:** Revised recommendations now properly weigh all factors instead of overreacting to the most recent input.

---

### 3. How Feedback Gets Structured

**Design Choice:** User feedback is stored as:
```python
{
    "selected_responses": {"A1": 1, "A2": 0, ...},  # 1=accept, 0=reject
    "new_assumptions": {"A6": "user's new consideration"}
}
```

**Why:** This separates "validating existing assumptions" from "introducing new factors". It makes it easier to see what the AI got right versus what it missed entirely.

---

### 4. Handling Invalid Input

**Implementation:** Used `while True` loops with proper error handling so users can't accidentally break the system.

**Why:** Better user experience - you get clear feedback if you type something unexpected, and you can fix it without restarting.

---

## Ideal Applications

**Good fit for:**
- Decisions where there's real uncertainty (no single "right" answer)
- Planning tasks (travel, career, major purchases)
- Situations with tradeoffs
- Value-laden choices (ethical dilemmas, policy decisions)
- Advisory contexts (health, finance, education)

**Not a good fit for:**
- Simple factual questions (no assumptions to negotiate)
- Math problems or calculations
- Classification tasks
- Anything with an objectively correct answer


**Interesting Use Cases**

- Sustainability Coaching: AI suggests lifestyle changes. User validates assumptions about feasibility, budget, preferences. System tailors advice to what's actually realistic for this person.

- Personalized Learning: Learning paths based on assumed prior knowledge. Student corrects assumptions about what they know/don't know. System adapts curriculum accordingly.

---

## Future Enhancements

### Web-Based User Interface
Right now it's command-line only. Adding a web UI (using Streamlit or Flask) would make it more accessible and visually intuitive. This is especially useful for showing assumption history and side-by-side comparisons.

### Assumption Weighting
Instead of binary accept/reject, let users rate importance (1-5 scale). Then generate recommendations that prioritize what matters most.

### Progressive Refinement & Memory
Enable multiple rounds of feedback within a session for iterative assumption refinement, and save validated assumptions across sessions to pre-populate user preferences over time. This creates personalized decision support.


### Explanation Feature
Add a "Why did you recommend this?" button that shows which assumptions most influenced the final recommendation. Makes the reasoning even more transparent.

### Multiple New Assumptions
Currently supports only one new consideration per session. Should extend to handle multiple.

### Comparison Mode
Generate multiple recommendations under different assumption sets and show them side-by-side. "Here's what I'd recommend if X is true versus if Y is true."

### Evaluation & Metrics Framework
Track system effectiveness through behavior change (critical thinking about recommendations), trust calibration (user control and appropriate skepticism), decision quality (satisfaction with revised recommendations), and system performance (assumption rejection rates, frequency of new considerations added).

---

## Technical Documentation

### Project Structure
```
hitl/
├── main.py              # Main program (208 lines)
├── requirements.txt     # Dependencies (anthropic)
└── README.md           # This file
```

### Key Functions

**`get_user_input(prompt)`**
Prompts user and returns their input. Pretty straightforward.

**`generate_initial_response(user_input)`**
Sends query to Claude, gets back a dict with recommendation + 5 assumptions.

**`get_human_feedback(response)`**
Displays assumptions interactively, collects accept/reject decisions, allows adding new considerations. Returns structured feedback.

**`generate_revised_response(response, feedback)`**
Filters to accepted assumptions only, adds new considerations, sends to Claude for balanced revision. Returns revised recommendation.

**`main()`**
Orchestrates the whole workflow.

---

## Development Notes

### Key Implementation Details

**Model:** Using `claude-sonnet-4-20250514` (good balance of capability and cost)

**Output Format:** Instructed Claude to return raw JSON with no markdown formatting. Makes parsing way cleaner.

**Error Handling:** Input validation with clear error messages. Users can't accidentally break things.

**Code Style:** PEP 8 compliant, fully documented with docstrings. Tried to keep it readable.

### Critical System Prompts

For the **initial response**, I tell Claude:
- "State assumptions in POSITIVE form, avoid double negatives"
- Makes assumptions clear and easy to confirm

For the **revised response**, I tell Claude:
- "Generate a revised recommendation that BALANCES ALL the accepted assumptions"
- "Do NOT let any single factor dominate the decision"
- Prevents new inputs from overshadowing everything else

---
## Final Thoughts

This project reinforced my interest in human-centered AI—systems that augment human judgment rather than replace it. The challenge isn't just about building performant AI; it's building AI that makes humans better critical thinkers. There's a lot more to explore here.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
