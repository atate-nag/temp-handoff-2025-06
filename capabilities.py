import matplotlib.pyplot as plt
import json


def plot_capabilities(capabilities):
    # Parse the JSON data
    # capabilities = json.loads(json_data)
    # Prepare lists for the x and y coordinates and labels
    x_coords = []
    y_coords = []
    labels = []

    # Calculate the coordinates for each capability
    for capability in capabilities:
        x_score = capability["scarcity"] + capability["non-replicability"]
        y_score = capability["value potential"] + capability["irreplaceability"]
        x_coords.append(x_score)
        y_coords.append(y_score)
        labels.append(capability["capability"])

    # Create a scatter plot
    fig, ax = plt.subplots(figsize=(8, 8))
    scatter = ax.scatter(x_coords, y_coords, color="blue")

    # Add labels for each point
    for label, x, y in zip(labels, x_coords, y_coords):
        ax.text(x, y, " " + label, ha="left", va="center", fontsize=9)

    # Define the maximum score for x and y axes to create a square plot
    max_score = max(max(x_coords), max(y_coords), 10)
    mid_point = max_score / 2

    # Draw quadrant lines at the half-way point
    ax.axhline(mid_point, color="black", linestyle="--", linewidth=1)
    ax.axvline(mid_point, color="black", linestyle="--", linewidth=1)

    # Set the axis labels
    ax.set_xlabel("Sustainability (Scarcity + Non-replicability)")
    ax.set_ylabel("Value Generation (Value Potential + Irreplaceability)")

    # Set axis labels for Low and High
    ax.text(0, -0.5, "Low", ha="center", va="center", fontsize=12)
    ax.text(max_score, -0.5, "High", ha="center", va="center", fontsize=12)
    ax.text(-0.5, 0, "Low", ha="center", va="center", fontsize=12, rotation=90)
    ax.text(-0.5, max_score, "High", ha="center", va="center", fontsize=12, rotation=90)

    # Set the axis ranges to be equal
    ax.set_xlim(0, max_score)
    ax.set_ylim(0, max_score)

    # Remove the axis numbers (ticks)
    ax.set_xticks([])
    ax.set_yticks([])

    # Add grid
    ax.grid(True, which="both", linestyle="--", linewidth=0.5)

    # Set background to white and adjust plot
    ax.set_facecolor("white")
    plt.tight_layout()

    # Show the plot
    return fig


# json_data = '''[
#     {
#         "capability": "Advanced Numerical Algorithm Development",
#         "value potential": 9,
#         "scarcity": 8,
#         "non-replicability": 7,
#         "irreplaceability": 9
#     },
#     {
#         "capability": "Hybrid Computational Approach Integration",
#         "value potential": 8,
#         "scarcity": 7,
#         "non-replicability": 6,
#         "irreplaceability": 8
#     },
#     {
#         "capability": "Machine Learning and AI Application Expertise",
#         "value potential": 8,
#         "scarcity": 6,
#         "non-replicability": 6,
#         "irreplaceability": 7
#     },
#     {
#         "capability": "High-Performance Computing (HPC) Solutions",
#         "value potential": 9,
#         "scarcity": 7,
#         "non-replicability": 7,
#         "irreplaceability": 9
#     },
#     {
#         "capability": "Adaptation to Emerging Computational Trends",
#         "value potential": 7,
#         "scarcity": 6,
#         "non-replicability": 5,
#         "irreplaceability": 6
#     },
#     {
#         "capability": "Industry-Specific Computational Solution Development",
#         "value potential": 8,
#         "scarcity": 7,
#         "non-replicability": 7,
#         "irreplaceability": 8
#     },
#     {
#         "capability": "Software Development and Integration Expertise",
#         "value potential": 8,
#         "scarcity": 6,
#         "non-replicability": 5,
#         "irreplaceability": 7
#     },
#     {
#         "capability": "Strategic Alliances and Collaborations",
#         "value potential": 7,
#         "scarcity": 5,
#         "non-replicability": 4,
#         "irreplaceability": 6
#     },
#     {
#         "capability": "Deep Domain Knowledge in Mathematical Modeling",
#         "value potential": 9,
#         "scarcity": 8,
#         "non-replicability": 8,
#         "irreplaceability": 9
#     },
#     {
#         "capability": "Commitment to Cutting-edge Research and Development",
#         "value potential": 8,
#         "scarcity": 7,
#         "non-replicability": 7,
#         "irreplaceability": 8
#     }
# ]'''
# json_data = '''[{"capability": "Integration with ML and DL Technologies", "value potential": 9, "scarcity": 7, "non-replicability": 6, "irreplaceability": 8}, {"capability": "HPDA Algorithm Development", "value potential": 8, "scarcity": 7, "non-replicability": 7, "irreplaceability": 8}, {"capability": "Agent-based Modelling Capabilities", "value potential": 7, "scarcity": 6, "non-replicability": 6, "irreplaceability": 7}, {"capability": "Symbolic Computing alongside Numerical Libraries", "value potential": 8, "scarcity": 7, "non-replicability": 6, "irreplaceability": 7}, {"capability": "Adaptation and Evolution in Competitive Environment", "value potential": 9, "scarcity": 8, "non-replicability": 8, "irreplaceability": 9}, {"capability": "Strategic Use of the Five Forces Analysis", "value potential": 7, "scarcity": 5, "non-replicability": 5, "irreplaceability": 6}, {"capability": "technical Excellence in Various Sectors", "value potential": 8, "scarcity": 6, "non-replicability": 7, "irreplaceability": 7}, {"capability": "Experienced and Highly Technical Team", "value potential": 9, "scarcity": 8, "non-replicability": 9, "irreplaceability": 9}, {"capability": "Innovation and Collaboration", "value potential": 8, "scarcity": 7, "non-replicability": 8, "irreplaceability": 8}, {"capability": "Cloud Solutions and HPC Expertise", "value potential": 8, "scarcity": 7, "non-replicability": 7, "irreplaceability": 8}, {"capability": "Established Reputation and Client Trust", "value potential": 9, "scarcity": 8, "non-replicability": 8, "irreplaceability": 9}]'''
#
#
# # Call the function with the JSON data

# plot_capabilities(json_data)
