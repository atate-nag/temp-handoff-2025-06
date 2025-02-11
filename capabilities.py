import json
import plotly.graph_objects as go
import plotly.express as px

def plot_capabilities(capabilities):
    # Parse the JSON data
    capabilities = json.loads(capabilities)

    # Extract coordinates and labels
    x_coords = []
    y_coords = []
    labels = []

    for capability in capabilities:
        x_score = capability["scarcity"] + capability["non-replicability"]
        y_score = capability["value potential"] + capability["irreplaceability"]
        x_coords.append(x_score)
        y_coords.append(y_score)
        labels.append(capability["capability"])

    # Determine the range based on min and max values
    min_x, max_x = min(x_coords) - 10, max(x_coords) + 10
    min_y, max_y = min(y_coords) - 10, max(y_coords) + 10

    # Create a DataFrame for easier manipulation
    import pandas as pd
    df = pd.DataFrame({
        'x': x_coords,
        'y': y_coords,
        'capability': labels
    })

    # Set aspect ratio for PowerPoint (16:9)
    width_px = 1280  # Width in pixels
    height_px = 720  # Height in pixels

    # Create the scatter plot using Plotly Express for easy color mapping
    fig = px.scatter(
        df,
        x='x',
        y='y',
        color='capability',
        labels={
            'x': 'Sustainability (Scarcity + NonReplicability)',
            'y': 'Value Generation (ValuePotential + Irreplaceability)'
        },
        color_discrete_sequence=px.colors.qualitative.Plotly,
        hover_data={'capability': True},
        width=width_px,
        height=height_px
    )

    # Adjust marker size and style
    fig.update_traces(
        marker=dict(
            size=15,  # Marker size can be adjusted based on preference
            line=dict(width=2, color='DarkSlateGrey'),
            symbol='circle'
        )
    )

    # Add quadrant lines at the midpoint of the current range
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    fig.add_shape(type="line",
                  x0=mid_x, y0=min_y, x1=mid_x, y1=max_y,
                  line=dict(color="gray", width=1, dash="dash"))
    fig.add_shape(type="line",
                  x0=min_x, y0=mid_y, x1=max_x, y1=mid_y,
                  line=dict(color="gray", width=1, dash="dash"))

    # Update axes properties to focus on relevant range
    fig.update_xaxes(
        range=[min_x, max_x],
        showticklabels=True,
        showgrid=True,
        gridcolor='lightgray'
    )
    fig.update_yaxes(
        range=[min_y, max_y],
        showticklabels=True,
        showgrid=True,
        gridcolor='lightgray'
    )

    # Adjust margins and layout
    fig.update_layout(
        margin=dict(l=100, r=100, t=100, b=100),
        plot_bgcolor='white',
        legend_title_text='Capabilities',
        font=dict(size=14),
        xaxis_title_font=dict(size=16),
        yaxis_title_font=dict(size=16),
        legend=dict(
            x=1.05,
            y=1,
            traceorder='normal',
            font=dict(size=10),
            bordercolor='Black',
            borderwidth=0.5
        )
    )

    # Show the plot
    fig.show()

    return fig

# Your JSON data
json_data = '''
[
    {"capability": "Global Market Penetration", "value potential": 90, "scarcity": 85, "non-replicability": 87, "irreplaceability": 88},
    {"capability": "Regulatory Compliance and Risk Management", "value potential": 88, "scarcity": 80, "non-replicability": 85, "irreplaceability": 87},
    {"capability": "Digital Transformation and Technological Innovation", "value potential": 92, "scarcity": 88, "non-replicability": 89, "irreplaceability": 90},
    {"capability": "Strategic Acquisitions and Market Expansion", "value potential": 85, "scarcity": 82, "non-replicability": 80, "irreplaceability": 84},
    {"capability": "Customer Trust and Relationship Management", "value potential": 90, "scarcity": 85, "non-replicability": 84, "irreplaceability": 89},
    {"capability": "Wealth Management and Investment Services", "value potential": 89, "scarcity": 87, "non-replicability": 86, "irreplaceability": 88},
    {"capability": "Financial Engineering and Complex Product Offerings", "value potential": 87, "scarcity": 80, "non-replicability": 83, "irreplaceability": 85},
    {"capability": "Operational Resilience and Crisis Management", "value potential": 88, "scarcity": 85, "non-replicability": 84, "irreplaceability": 87},
    {"capability": "Thought Leadership and Industry Influence", "value potential": 84, "scarcity": 78, "non-replicability": 80, "irreplaceability": 83},
    {"capability": "Data Management and Cybersecurity Expertise", "value potential": 90, "scarcity": 85, "non-replicability": 82, "irreplaceability": 88}
]
'''

# Call the function with the JSON data
fig = plot_capabilities(json_data)
