
import os
import json
from anthropic import Anthropic

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
    llm_input_data = {
        "old_recommendation": {},
        "assumptions": {}
    }

    # Add the old recommendation as context for the LLM
    llm_input_data["old_recommendation"] = response["recommendation"]

    # Add accepted assumptions from feedback
    for key, value in feedback["selected_responses"].items():
        if value == 1:
            llm_input_data["assumptions"][key] = response["assumptions"][key]
    
    # Add new assumptions from feedback
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
        messages=[{"role": "user", "content": f"""
                    INITIAL RECOMMENDATION: 
                        {llm_input_data["old_recommendation"]}
                    
                    ACCEPTED ASSUMPTIONS (user confirmed these are correct): 
                        {json.dumps(llm_input_data["assumptions"], indent=2)}

                    Please generate a REVISED recommendation that balances ALL these accepted assumptions.
                    No single factor should dominate - consider the trade-offs.
                """
                }]
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