from dash import Dash, html, dash_table
import pandas as pd
import datetime
import datetime
from data_store import Data_store
from dash import Dash, dcc, html, Input, Output, callback
import plotly
import tiktoken

import os

from pydantic import BaseModel

encoding = tiktoken.get_encoding("cl100k_base")

data_store = Data_store()


class stability_test(BaseModel):
    name: str
    value: int
    description: str


class llm_call(BaseModel):
    model: str
    data: dict
    nb_tokens: int
    temperature: float
    success: bool


class step_call(BaseModel):
    step_name: str
    parameters: dict


# Create a Dash app

external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

app = Dash(__name__, external_stylesheets=external_stylesheets)
# app.layout = html.Div(
#     html.Div(
#         [
#             html.H4("TERRA Satellite Live Feed"),
#             html.Div(id="live-update-text"),
#             dcc.Graph(id="live-update-graph"),
#             dcc.Interval(
#                 id="interval-component",
#                 interval=1 * 1000,  # in milliseconds
#                 n_intervals=0,
#             ),
#         ]
#     )
# )
try:
    data_table, labels = data_store.load("metadata_llm_call")
except:
    data_table = []
    labels = []
app.layout = html.Div(
    [
        dcc.Interval(
            id="interval-component",
            interval=1 * 2000,  # in milliseconds
            n_intervals=0,
        ),
        dash_table.DataTable(data_table, labels, id="tbl"),
    ]
)


@callback(
    [Output("tbl", "data"), Output("tbl", "columns")],
    Input("interval-component", "n_intervals"),
)
def update_table(n):
    data_store.read_data("data_store/input")
    print("Loading LLM CALLS")
    try:
        data_table, labels = data_store.load("llm_call")
    except Exception as e:
        print(f"Error: {e}")
        data_table = []
        labels = []
    return data_table, labels


# @callback(
#     Output("live-update-text", "children"), Input("interval-component", "n_intervals")
# )
# def update_metrics(n):
#     lon, lat, alt = data_store.get_lonlatalt(datetime.datetime.now())
#     style = {"padding": "5px", "fontSize": "16px"}
#     return [
#         html.Span("Longitude: {}".format(lon), style=style),
#         html.Span("Latitude: {}".format(lat), style=style),
#         html.Span("Altitude: {}".format(alt), style=style),
#     ]


# # Multiple components can update everytime interval gets fired.
# @callback(
#     Output("live-update-graph", "figure"), Input("interval-component", "n_intervals")
# )
# def update_graph_live(n):
#     data = {"time": [], "Latitude": [], "Longitude": [], "Altitude": []}

#     # Collect some data
#     for i in range(180):
#         time = datetime.datetime.now() - datetime.timedelta(seconds=i * 20)
#         lon_, lat_, alt_ = data_store.get_lonlatalt(time)
#         for lon, lat, alt in zip(lon_, lat_, alt_):
#             data["Longitude"].append(lon)
#             data["Latitude"].append(lat)
#             data["Altitude"].append(alt)
#             data["time"].append(time)

#     # Create the graph with subplots
#     fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
#     fig["layout"]["margin"] = {"l": 30, "r": 10, "b": 30, "t": 10}
#     fig["layout"]["legend"] = {"x": 0, "y": 1, "xanchor": "left"}

#     fig.append_trace(
#         {
#             "x": data["time"],
#             "y": data["Altitude"],
#             "name": "Altitude",
#             "mode": "lines+markers",
#             "type": "scatter",
#         },
#         1,
#         1,
#     )
#     fig.append_trace(
#         {
#             "x": data["Longitude"],
#             "y": data["Latitude"],
#             "text": data["time"],
#             "name": "Longitude vs Latitude",
#             "mode": "lines+markers",
#             "type": "scatter",
#         },
#         2,
#         1,
#     )

#     return fig


if __name__ == "__main__":
    app.run(debug=True)
