import plotly.graph_objs as go
import numpy as np
import json, os
from typing import Dict, List


def generate_trend_radar(categories):
    # Parse the JSON data

    # Initialize figure
    fig = go.Figure()

    # Define the category angles
    num_categories = len(categories)
    angles = np.linspace(
        start=0, stop=2 * np.pi, num=num_categories, endpoint=False
    ).tolist()

    # Define the readiness color scale
    readiness_color_map = {
        "low": "red",  # Low readiness
        "medium": "yellow",  # Medium readiness
        "high": "green",  # High readiness
    }

    # Function to map readiness value to color
    def map_readiness_to_color(readiness):
        if readiness >= 8:
            return readiness_color_map["high"]
        elif readiness >= 6:
            return readiness_color_map["medium"]
        else:
            return readiness_color_map["low"]

    # Add trends for each category
    for idx, (category, trend_list) in enumerate(categories.items()):
        for trend in trend_list:
            # Map the readiness to a color
            readiness_color = map_readiness_to_color(trend["readiness"])

            # Add trace for each trend
            fig.add_trace(
                go.Scatterpolar(
                    r=[
                        11 - trend["importance"]
                    ],  # Inverted importance for radial position
                    theta=[angles[idx] * (180 / np.pi)],  # Angle in degrees
                    text=trend["trend"],
                    name=category,
                    marker=dict(
                        size=trend["likelihood"] * 10,  # Size for likelihood
                        color=readiness_color,
                    ),
                    mode="markers+text",
                    textposition="top center",
                )
            )

    # Customize layout
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], autorange="reversed"),
            angularaxis=dict(showticklabels=False),
        ),
        title="Trend Radar",
        showlegend=True,
    )

    # Add category labels at the mean angle for each segment
    for i, category_name in enumerate(categories.keys()):
        angle = angles[i] + (angles[1] - angles[0]) / 2
        if angle > np.pi:
            angle -= 2 * np.pi  # Adjust angle for correct text orientation

        # Positioning annotations correctly on the plot
        fig.add_annotation(
            text=category_name,
            xref="paper",
            yref="paper",
            x=(0.5 + 0.5 * np.cos(angle)),  # Normalized x position
            y=(0.5 + 0.5 * np.sin(angle)),  # Normalized y position
            showarrow=False,
            font=dict(size=12),
            textangle=(
                np.degrees(angle) - 90 if np.cos(angle) < 0 else np.degrees(angle) + 90
            ),
            xanchor="center",
            yanchor="middle",
        )
        radial_distance_for_annotations = (
            11  # Assuming the range is [0, 10] and adding 1 for padding
        )

    return fig
def save_trend_radar_png(categories: dict, company: str) -> str:
    fig = generate_trend_radar(categories)
    out_dir = "./Strategic Reports"
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, f"{company}_trend_radar.png")

    # -- try to write (needs kaleido) ----------------------------------
    fig.write_image(png_path, scale=2)

    # ---- sanity-check: raise if the file is still missing -----------
    if not os.path.isfile(png_path):
        raise RuntimeError(
            f"[trend-radar] Could not write PNG – do you have `kaleido` installed?"
        )
    return png_path
