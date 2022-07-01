import datetime
import json
import os
import dash
import plotly

import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from minio import Minio
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

minio_client = Minio(os.environ['MINIO_HOST'],
                     access_key=os.environ['MINIO_ACCESS_KEY'],
                     secret_key=os.environ['MINIO_SECRET_KEY'],
                     secure=False)

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div(
    html.Div([
        html.H4('Sensor data (Demo vehicle)'),
        dcc.Graph(id='live-update-graph'),
        dcc.Interval(
            id='interval-component',
            interval=2*1000,  # in milliseconds
            n_intervals=0
        )
    ])
)

# Multiple components can update everytime interval gets fired.
@app.callback(Output('live-update-graph', 'figure'),
              [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
    h_timestamps = []
    h_values = []
    t_timestamps = []
    t_values = []
    humidity_objects = minio_client.list_objects('data', prefix='humidity')
    temperature_objects = minio_client.list_objects('data', prefix='temperature')

    for object in humidity_objects:
        response = minio_client.get_object('data', object.object_name.encode('utf-8'))
        json_data = json.loads(response.data)
        h_timestamps.append(json_data['time'])
        h_values.append(json_data['humidity'])

    for object in temperature_objects:
        response = minio_client.get_object('data', object.object_name.encode('utf-8'))
        json_data = json.loads(response.data)
        t_timestamps.append(json_data['time'])
        t_values.append(json_data['temperature'])

    # Create the graph with subplots
    fig = plotly.subplots.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
    fig['layout']['margin'] = {
        'l': 30, 'r': 10, 'b': 30, 't': 10
    }
    fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'left'}

    fig.append_trace({
        'x': h_timestamps,
        'y': h_values,
        'name': 'Humidity',
        'mode': 'lines+markers',
        'type': 'scatter'
    }, 1, 1)
    fig.append_trace({
        'x': t_timestamps,
        'y': t_values,
        'name': 'Temperature',
        'mode': 'lines+markers',
        'type': 'scatter'
    }, 2, 1)

    return fig


if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8080, debug=True)
