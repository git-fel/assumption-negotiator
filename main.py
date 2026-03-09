
import os
import json
from anthropic import Anthropic
from prompts import INITIAL_SYSTEM_PROMPT, REVISE_SYSTEM_PROMPT

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))  # set this environment variable with API key

def get_user_input(prompt):
    """Prompt the user for input and return their response."""
    return input(prompt) 

def generate_initial_response(user_input):
    """
    Generate initial recommendation with supporting assumptions.
    
    Sends user query to Claude API with instructions to provide:
    - A recommendation addressing the query
    - 5 key assumptions stated in positive form
    
    Args:
        user_input (str): The user's query
    
    Returns:
        dict: Dictionary with keys:
            - 'recommendation': str, the suggested action
            - 'assumptions': nested dict, 5 assumptions as {A1: str, A2: str, ...}
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=INITIAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_input}]
    )
    llm_response_text = response.content[0].text  #structured format but in text form
    initial_response = json.loads(llm_response_text)  #convert to dict for Python processing
    return initial_response


def get_human_feedback(response):
    """
    Collect user feedback on assumptions through interactive prompts.
    
    For each assumption in the initial response:
    - Displays the assumption to the user
    - Prompts for acceptance (yes/no)
    - Records 1 for acceptance, 0 for rejection
    
    Also prompts user to add new considerations they want the system
    to take into account.
    
    Args:
        response (dict): Initial LLM response with 'recommendation' and 'assumptions' keys
    
    Returns:
        dict: User feedback with structure:
            - 'selected_responses': {assumption_id: 1 or 0, ...}
            - 'new_assumptions': {new_id: new_assumption_text} or empty dict
    """

    feedback = {
        "selected_responses": {},
        "new_assumptions": {}
    }

    print(f"\nTHIS RECOMMENDATION IS BASED ON THE FOLLOWING ASSUMPTIONS. PLEASE REVIEW THEM:")
    for key, value in response["assumptions"].items():
        print(f"\n{key}: {value}")
        while True:
            user_input = input("IS THIS ASSUMPTION CORRECT? (yes/no): ")
            if user_input.strip().lower() == "yes":
                feedback["selected_responses"][key] = 1
                break
            elif user_input.strip().lower() == "no":
                feedback["selected_responses"][key] = 0
                break
            else:
                print("INVALID INPUT. ")
    
    while True:
        new_input = input("DO YOU WANT THE SYSTEM TO CONSIDER ANY NEW FACTOR? (yes/no): ")
        if new_input.strip().lower() == "yes":
            new_assumption = input("PLEASE ENTER THE NEW CONSIDERATION: ")
            new_assumption_id = "A" + str(len(response["assumptions"]) + 1)  # Generate new assumption ID
            feedback["new_assumptions"] = {new_assumption_id: new_assumption}
            break
        elif new_input.strip().lower() == "no":
            feedback["new_assumptions"] = {}
            break
        else:
            print("INVALID INPUT. ")

    return feedback


def generate_revised_response(response, feedback):
    """
    Generate revised recommendation based on user-validated assumptions.
    
    Process:
    1. Filters initial assumptions to keep only those accepted by user (value=1)
    2. Adds any new assumptions provided by user
    3. Sends filtered assumption set to Claude API with instructions to generate
       a balanced recommendation that considers all assumptions equally

    Args:
        response (dict): Initial LLM response with 'recommendation' and 'assumptions'
        feedback (dict): User feedback with structure:
            - 'selected_responses': {assumption_id: 1 or 0, ...}
            - 'new_assumptions': {new_id: new_text} or empty dict

    Returns:
        dict: Revised LLM response with updated 'recommendation' and 'assumptions' keys
            - 'recommendation': str, the balanced revised suggestion
            - 'assumptions': dict, the validated and new assumptions

    """
    # Separate the user's feedback into two clear groups:
    # - accepted: the user confirmed these are TRUE for their situation
    # - rejected: the user said these are FALSE — they actively contradict the original reasoning
    accepted = {}
    rejected = {}
    for key, value in feedback["selected_responses"].items():
        if value == 1:
            accepted[key] = response["assumptions"][key]
        else:
            rejected[key] = response["assumptions"][key]

    new_considerations = feedback.get("new_assumptions", {})

    api_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=REVISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"""
                    INITIAL RECOMMENDATION (based on unverified assumptions — may no longer be valid):
                        {response["recommendation"]}

                    ACCEPTED ASSUMPTIONS — the user confirmed these are TRUE for their situation:
                        {json.dumps(accepted, indent=2) if accepted else "(none accepted)"}

                    REJECTED ASSUMPTIONS — the user confirmed these are FALSE for their situation:
                        {json.dumps(rejected, indent=2) if rejected else "(none rejected)"}

                    NEW CONSIDERATIONS added by the user:
                        {json.dumps(new_considerations, indent=2) if new_considerations else "(none added)"}

                    Generate a REVISED recommendation grounded in the accepted assumptions and new considerations.
                    The rejected assumptions should shape what you do NOT recommend.
                    If any rejected assumption was central to the original recommendation, your revised
                    recommendation must meaningfully differ from the original.
                """}]
    )

    revised_response = json.loads(api_response.content[0].text)  #convert to dict for Python processing
    return revised_response

def main():
    """
    Run the assumption negotiation assistant.
    Orchestrates the full workflow: get user query, generate initial recommendation,
    collect feedback on assumptions, and generate revised recommendation.
    """
    user_input = get_user_input("PLEASE ENTER YOUR QUERY: ")
    initial_response = generate_initial_response(user_input)
    print(f"\nINITIAL RECOMMENDATION: {initial_response['recommendation']}\n")

    feedback = get_human_feedback(initial_response)
    
    revised_response = generate_revised_response(initial_response, feedback)
    print(f"\nREVISED RECOMMENDATION: {revised_response['recommendation']}\n")


if __name__ == "__main__":
    main()