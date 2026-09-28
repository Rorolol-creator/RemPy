import base64
import os
from turtle import title
from matplotlib import matplotlib_fname
import numpy as np
import imageio.v3 as iio
import matplotlib
import plotly.graph_objects as go

from dash import *
from dash import no_update
import requests
import json

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app = Dash()


def save_upload(contents, filename):
    _, content_string = contents.split(",")
    data = base64.b64decode(content_string)
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path


def normalize(arr):
    arr = arr.astype(float)
    arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-9)
    return (arr * 255).astype(np.uint8)


# website buttons texts etc

app.layout = html.Div(
    [
        html.H3("Geodesic Propagation Benchmark"),
        html.Div(
            [
                html.Label("Upload Image:"),
                dcc.Upload(id="img-up", children=html.Button("Select Image")),
                html.Div(
                    id="img-feedback", style={"marginTop": "5px", "color": "green"}
                ),
            ],
            style={"margin": "10px"},
        ),
        html.Div(
            [
                html.Label("Upload Mask:"),
                dcc.Upload(id="mask-up", children=html.Button("Select Mask")),
                html.Div(
                    id="mask-feedback", style={"marginTop": "5px", "color": "green"}
                ),
            ],
            style={"margin": "10px"},
        ),
        html.Button("Run Benchmark", id="run", style={"margin": "20px"}),
        html.Hr(),
        html.Div(id="error-message", style={"color": "red"}),
        dcc.Loading(
            type="circle",
            children=html.Div(
                [
                    dcc.Graph(id="timing-plot"),
                    html.Div(
                        id="timing-table",
                        style={"display": "flex", "justifyContent": "center"},
                    ),
                    html.H4("Resulting Benchmarks"),
                    html.Div(
                        [
                            html.Img(
                                id="result-img-base",
                                style={"maxWidth": "400px", "marginRight": "10px"},
                                title="Custom benchmark",
                            ),
                            html.Img(
                                id="result-img-inferno",
                                style={"maxWidth": "400px"},
                                title="NJIT benchmark",
                            ),
                        ],
                        style={"display": "flex", "justifyContent": "center"},
                    ),
                    html.H4("Benchmark History"),
                    html.Div(
                        id="history-table",
                        style={"display": "flex", "justifyContent": "center"},
                    ),
                ]
            ),
        ),
    ],
    style={
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "justifyContent": "flex-start",
        "textAlign": "center",
        "minHeight": "100vh",
        "gap": "10px",
        "background": "linear-gradient(135deg, #f0f2f5, #d9e2f3)",
        "padding": "20px",
    },
)

# callback


@app.callback(
    Output("img-feedback", "children"),
    Output("mask-feedback", "children"),
    Input("img-up", "filename"),
    Input("mask-up", "filename"),
)
def update_feedback(img_name, mask_name):
    img_msg = f"Selected: {img_name}" if img_name else "No image selected"
    mask_msg = f"Selected: {mask_name}" if mask_name else "No mask selected"
    return img_msg, mask_msg


@app.callback(
    Output("timing-plot", "figure", allow_duplicate=True),
    Output("timing-table", "children", allow_duplicate=True),
    Output("result-img-base", "src", allow_duplicate=True),
    Output("result-img-inferno", "src", allow_duplicate=True),
    Output("history-table", "children", allow_duplicate=True),
    Output("error-message", "children", allow_duplicate=True),
    Input("run", "n_clicks"),
    State("img-up", "contents"),
    State("img-up", "filename"),
    State("mask-up", "contents"),
    State("mask-up", "filename"),
    prevent_initial_call=True,
)
def run_benchmark(n, img_contents, img_name, mask_contents, mask_name):

    if not img_contents or not mask_contents:
        return "Files not uploaded"

    # save files
    img_path = save_upload(img_contents, img_name)
    mask_path = save_upload(mask_contents, mask_name)

    payload = {"img": open(img_path, "rb"), "mask": open(mask_path, "rb")}

    response = requests.post("http://backend:8000/propagate", files=payload)
    if not response.ok:
        try:
            error_msg = response.json().get("detail", "Unknown backend error")
        except:
            error_msg = response.text

        return no_update, no_update, None, None, no_update, error_msg

    loaded = response.json()

    res_custom, t_custom, res_njit, t_njit = (
        loaded["bytes_custom"],
        loaded["t_custom"],
        loaded["bytes_njit"],
        loaded["t_njit"],
    )

    shape = tuple(map(int, loaded["shape"].strip("()").split(",")))

    res_custom = np.frombuffer(base64.b64decode(res_custom), dtype=np.float64).reshape(
        shape
    )
    res_njit = np.frombuffer(base64.b64decode(res_njit), dtype=np.int64).reshape(shape)

    # get both images
    normed_njit = (res_njit - res_njit.min()) / (res_njit.max() - res_njit.min() + 1e-9)
    cmap_njit = matplotlib.colormaps["inferno"]
    disp_inferno_njit = (cmap_njit(normed_njit)[:, :, :3] * 255).astype(np.uint8)

    normed_custom = (res_custom - res_custom.min()) / (
        res_custom.max() - res_custom.min() + 1e-9
    )
    cmap_custom = matplotlib.colormaps["viridis"]
    disp_inferno_custom = (cmap_custom(normed_custom)[:, :, :3] * 255).astype(np.uint8)

    # save both images
    out_inferno_custom = os.path.join(UPLOAD_DIR, "result_inferno_custom.png")
    iio.imwrite(out_inferno_custom, disp_inferno_custom)

    out_inferno_njit = os.path.join(UPLOAD_DIR, "result_inferno_njit.png")
    iio.imwrite(out_inferno_njit, disp_inferno_njit)

    # encode for dash
    with open(out_inferno_njit, "rb") as f:
        encoded_njit = base64.b64encode(f.read()).decode()
    src_njit = f"data:image/png;base64,{encoded_njit}"

    with open(out_inferno_custom, "rb") as f:
        custom_inferno = base64.b64encode(f.read()).decode()
    src_custom = f"data:image/png;base64,{custom_inferno}"

    # graph creation
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["Custom", "NJIT"],
            y=[t_custom, t_njit],
            text=[f"{t_custom:.4f}s", f"{t_njit:.4f}s"],
            textposition="auto",
            marker_color=["blue", "green"],
        )
    )
    fig.update_layout(title="Execution Time Comparison", yaxis_title="Time (seconds)")

    # table creation
    table = html.Table(
        [
            html.Tr([html.Th("Methods'"), html.Th("Execution Times")]),
            html.Tr([html.Td("Custom"), html.Td(f"{t_custom:.6f}")]),
            html.Tr([html.Td("NJIT"), html.Td(f"{t_njit:.6f}")]),
        ]
    )

    history = requests.get("http://database:6000/all").json()

    history_table = html.Table(
        [
            html.Tr(
                [
                    html.Th("Image"),
                    html.Th("Mask"),
                    html.Th("Custom (s)"),
                    html.Th("NJIT (s)"),
                ]
            )
        ]
        + [
            html.Tr(
                [
                    html.Td(
                        html.Button(
                            row["image"],
                            id={"type": "history-btn", "id": row["id"]},
                            n_clicks=0,
                            style={
                                "background": "none",
                                "border": "none",
                                "color": "blue",
                                "cursor": "pointer",
                            },
                        )
                    ),
                    html.Td(row["mask"]),
                    html.Td(f"{row['t_custom']:.6f}"),
                    html.Td(f"{row['t_njit']:.6f}"),
                ]
            )
            for row in history
        ]
    )

    return fig, table, src_njit, src_custom, history_table, ""


def array_to_dash_src(arr, cmap_name):
    normed = (arr - arr.min()) / (arr.max() - arr.min() + 1e-9)
    cmap = matplotlib.colormaps[cmap_name]
    rgb = (cmap(normed)[:, :, :3] * 255).astype(np.uint8)

    import io

    buffer = io.BytesIO()
    iio.imwrite(buffer, rgb, extension=".png")
    buffer.seek(0)

    encoded = base64.b64encode(buffer.read()).decode()
    return f"data:image/png;base64,{encoded}"


@app.callback(
    Output("timing-plot", "figure"),
    Output("timing-table", "children"),
    Output("result-img-base", "src"),
    Output("result-img-inferno", "src"),
    Input({"type": "history-btn", "id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def load_from_history(n_clicks_list):
    if ctx.triggered[0]["value"] == 0:
        return no_update, no_update, no_update, no_update

    clicked_id = ctx.triggered[0]["prop_id"].split(".")[0]
    clicked_id = json.loads(clicked_id)

    response = requests.get(
        "http://database:6000/specific",
        params={"id": clicked_id["id"]},
    )

    data = response.json()

    if not data.get("exists"):
        return no_update, no_update, no_update, no_update

    shape = tuple(map(int, data["shape"].strip("()").split(",")))

    res_custom = np.frombuffer(
        base64.b64decode(data["bytes_custom"]),
        dtype=np.float64,
    ).reshape(shape)

    res_njit = np.frombuffer(
        base64.b64decode(data["bytes_njit"]),
        dtype=np.int64,
    ).reshape(shape)

    t_custom = data["t_custom"]
    t_njit = data["t_njit"]

    src_custom = array_to_dash_src(res_custom, "inferno")
    src_njit = array_to_dash_src(res_njit, "viridis")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["Custom", "NJIT"],
            y=[t_custom, t_njit],
            text=[f"{t_custom:.4f}s", f"{t_njit:.4f}s"],
            textposition="auto",
            marker_color=["blue", "green"],
        )
    )
    fig.update_layout(title="Execution Time Comparison", yaxis_title="Time (seconds)")

    table = html.Table(
        [
            html.Tr([html.Th("Methods"), html.Th("Execution Time")]),
            html.Tr([html.Td("Custom"), html.Td(f"{t_custom:.6f}")]),
            html.Tr([html.Td("NJIT"), html.Td(f"{t_njit:.6f}")]),
        ]
    )

    return fig, table, src_custom, src_njit


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)
