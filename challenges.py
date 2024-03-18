import matplotlib.pyplot as plt
import json
import matplotlib.pyplot as plt


def plot_challenges(challenges):
    # Prepare lists for the x and y coordinates and labels
    x_coords = []
    y_coords = []
    labels = []

    # Calculate the coordinates for each challenge
    for challenge in challenges:
        x_score = challenge["importance"]
        y_score = challenge["addressability"]
        x_coords.append(x_score)
        y_coords.append(y_score)
        labels.append(
            challenge["challenge"]
        )  # Adjusted for correct attribute 'challenge'

    # Create a scatter plot with larger figure size for better visibility
    fig, ax = plt.subplots(figsize=(10, 8))  # Adjust the figure size as needed
    scatter = ax.scatter(
        x_coords, y_coords, s=100, alpha=0.6, color="blue"
    )  # Adjust size as needed

    # Add labels for each point
    for label, x, y in zip(labels, x_coords, y_coords):
        ax.text(x, y, " " + label, ha="right", va="bottom", fontsize=9, wrap=True)

    # Set the axis labels, title, etc.
    # Your existing code here to set up the plot...

    # IMPORTANT: Return the figure object instead of plt
    return fig


def find_top_right_challenge(challenges):
    if isinstance(challenges, str):
        challenges = json.loads(challenges)
    max_combined_score = 0
    top_right_challenge = None
    # Iterate through the challenges to find the one with the highest combined score
    for challenge in challenges:
        combined_score = challenge["importance"] + challenge["addressability"]
        if combined_score > max_combined_score:
            max_combined_score = combined_score
            top_right_challenge = challenge

    json_top_right_challenge = json.dumps(top_right_challenge)
    return top_right_challenge


# # #
# str_challenges = '''[
#     {
#       "challenge": "Hardware vendors dominating core math libraries.",
#       "importance": 8.5,
#       "addressability": 4.0
#     },
#     {
#       "challenge": "Integration of AI and Machine Learning in mathematical libraries.",
#       "importance": 9.5,
#       "addressability": 9.2
#     },
#     {
#       "challenge": "Rise of open-source and free software impacting pricing models.",
#       "importance": 7.5,
#       "addressability": 8.2
#     },
#     {
#       "challenge": "Increased focus on high-performance computing capabilities.",
#       "importance": 8.5,
#       "addressability": 8.2
#     },
#     {
#       "challenge": "Strategic partnerships among competitors for market share.",
#       "importance": 6.5,
#       "addressability": 7.8
#     },
#     {
#       "challenge": "Stricter data privacy and security regulations.",
#       "importance": 7.5,
#       "addressability": 8.2
#     },
#     {
#       "challenge": "Policies fostering open science and reproducibility of research.",
#       "importance": 5.5,
#       "addressability": 7.2
#     },
#     {
#       "challenge": "International trade agreements affecting software imports/exports.",
#       "importance": 5.5,
#       "addressability": 4.0
#     },
#     {
#       "challenge": "Government investments in AI and computational research.",
#       "importance": 8.5,
#       "addressability": 8.8
#     },
#     {
#       "challenge": "Emerging patent laws and intellectual property strategies.",
#       "importance": 6.0,
#       "addressability": 7.5
#     },
#     {
#       "challenge": "Advancements in quantum computing impacting computational algorithms.",
#       "importance": 8.0,
#       "addressability": 8.5
#     },
#     {
#       "challenge": "Development of specialized AI chips influencing software optimization.",
#       "importance": 8.0,
#       "addressability": 8.5
#     },
#     {
#       "challenge": "Growth in cloud computing requiring scalable libraries.",
#       "importance": 9.0,
#       "addressability": 9.0
#     },
#     {
#       "challenge": "Need for energy-efficient computing algorithms.",
#       "importance": 6.5,
#       "addressability": 7.8
#     },
#     {
#       "challenge": "Utilization of blockchain for secure computational transactions.",
#       "importance": 4.5,
#       "addressability": 6.8
#     },
#     {
#       "challenge": "Increasing emphasis on ethical AI and algorithms.",
#       "importance": 7.5,
#       "addressability": 8.2
#     },
#     {
#       "challenge": "Growing public awareness and concern over data privacy.",
#       "importance": 8.5,
#       "addressability": 8.8
#     },
#     {
#       "challenge": "Demand for transparent and explainable AI.",
#       "importance": 7.0,
#       "addressability": 8.0
#     },
#     {
#       "challenge": "Collaboration in scientific research through open-source contributions.",
#       "importance": 6.0,
#       "addressability": 7.5
#     },
#     {
#       "challenge": "Focus on reducing the digital divide in technology access.",
#       "importance": 5.5,
#       "addressability": 7.2
#     },
#     {
#       "challenge": "Global economic uncertainties affecting R&D investments.",
#       "importance": 6.5,
#       "addressability": 4.0
#     },
#     {
#       "challenge": "Increase in technology-focused venture capital investments.",
#       "importance": 7.5,
#       "addressability": 8.2
#     },
#     {
#       "challenge": "Fluctuating currency exchange rates impacting international business.",
#       "importance": 5.5,
#       "addressability": 4.0
#     },
#     {
#       "challenge": "Growing importance of emerging markets as innovation centers.",
#       "importance": 6.5,
#       "addressability": 6.8
#     },
#     {
#       "challenge": "Shift towards remote work influencing software development practices.",
#       "importance": 7.5,
#       "addressability": 4.0
#     }
#   ]'''
# # # Call the function with the JSON data
# challenges = json.loads(str_challenges)
# plot_challenges(challenges)
# top_challenge = find_top_right_challenge(challenges)
#
# print(top_challenge)
