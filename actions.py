import json

def print_actions_pretty(actions):

    # Print each action in a formatted way
    for action in actions:
        print(f"Action: {action['action']}")
        print(f"How: {action['how']}")
        print(f"Who: {action['who']}")
        print("-" * 80)  # Separator line for readability


# # Example JSON data for actions
# actions_json = json.dumps([
#     {"action": "Immediately make the company adaptive to pursue opportunities",
#      "how": "revise backoffice and new sales program", "who": "Executives, sales leaders"},
#     {"action": "Streamline logistics", "how": "Implement new logistics software", "who": "Logistics department"},
#     {"action": "Improve customer service", "how": "Training program for support staff",
#      "who": "Customer support manager"}
#     # ... add more actions as needed
# ])
# # Call the function to print the actions
# print_actions_pretty(actions_json)
# actions_str = '''[
#     {"action": "Immediately make the company adaptive to pursue opportunities",
#      "how": "revise backoffice and new sales program", "who": "Executives, sales leaders"},
#     {"action": "Streamline logistics", "how": "Implement new logistics software", "who": "Logistics department"},
#     {"action": "Improve customer service", "how": "Training program for support staff",
#      "who": "Customer support manager"}
# ]
# '''
# actions = json.loads(actions_str)
# print_actions_pretty(actions)