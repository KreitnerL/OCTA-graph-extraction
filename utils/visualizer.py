import csv
import math
from random import random
from typing import Literal
from warnings import deprecated

import numpy as np
import pandas as pd
from matplotlib import cm, collections
from matplotlib import pyplot as plt
from matplotlib.patches import Circle
from PIL import Image


def rasterize_forest(forest: dict,
                     image_scale_factor: np.ndarray,
                     radius_list:list=None, 
                     min_radius=0,
                     max_radius=1,
                     max_dropout_prob=0,
                     blackdict: dict[str, bool]=None,
                     colorize=False,
                     thresholds=None):
    # initialize canvas with defined image dimensions
    if not radius_list:
        radius_list=[]
    image_dim = tuple([math.ceil(image_scale_factor * d) for d in [76,76]])
    no_pixels_x, no_pixels_y = image_dim
    dpi = 100
    x_inch = no_pixels_x / dpi
    y_inch = no_pixels_y / dpi
    figure = plt.figure(figsize=(x_inch,y_inch))
    figure.patch.set_facecolor('black')
    ax = plt.axes([0., 0., 1., 1.], frameon=False, xticks=[], yticks=[])
    ax.invert_yaxis()
    edges = []
    radii = []
    if blackdict is None:
        blackdict = dict()
        p = random()**10 * max_dropout_prob
    else:
        p=0
    for edge in forest:
        radius = float(edge["radius"])
        if radius<min_radius or radius>max_radius:
            continue
        current_node = edge["node1"]
        proximal_node = edge["node2"]

        if isinstance(current_node, np.ndarray) or isinstance(current_node, list):
            current_node = tuple(current_node)
            proximal_node = tuple(proximal_node)
        elif isinstance(current_node, str):
            # Legacy
            current_node = tuple([float(coord) for coord in current_node[1:-1].split(" ") if len(coord)>0])
            proximal_node = tuple([float(coord) for coord in proximal_node[1:-1].split(" ") if len(coord)>0])

        if proximal_node in blackdict or random()<p:
            blackdict[current_node] = True
            continue

        radius_list.append(radius)
        thickness = radius * no_pixels_x
        edges.append([(current_node[1],current_node[0]),(proximal_node[1],proximal_node[0])])
        radii.append(thickness)
    if colorize:
        colors=np.copy(np.array(radii))
        colors = colors/no_pixels_x/1.3*3*2
        if thresholds is None:
            colors=np.minimum(colors/0.03,1)
        else:
            c_new = np.zeros_like(colors)
            intensities = np.linspace(0.1,1, num=len(thresholds)+1)
            thresholds = [0,*thresholds,math.inf]
            for i in range(1,len(thresholds)):
                c_new[(thresholds[i-1]<colors) & (colors<=thresholds[i])]=intensities[i-1]
            colors=c_new
        colors=cm.plasma(colors)
    else:
        colors="w"
    ax.add_collection(collections.LineCollection(edges, linewidths=radii, colors=colors, antialiaseds=True, capstyle="round"))
    figure.canvas.draw()
    data = np.frombuffer(figure.canvas.buffer_rgba(), dtype=np.uint8)
    img = data.reshape(figure.canvas.get_width_height()[::-1] + (4,))
    img = img[:, :, :3]
    plt.close(figure)

    if colorize:
        img_gray = np.array(img.astype(np.float32))
    else:
        img_gray = np.array(Image.fromarray(img).convert("L")).astype(np.uint16)
    return img_gray, blackdict

@deprecated("Use generate_image_from_graph_json instead")
def node_edges_to_graph(nodes_file_path: str, edges_file_path: str, shape: tuple[int], colorize=False, radius_scale_factor=-1, thresholds=None) -> np.ndarray:
    nodes = dict()
    with open(nodes_file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        for row in reader:
            nodes[row["id"]] = [float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"])]
    
    img = np.zeros(shape[:2])
    with open(edges_file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile,delimiter=";")
        forest = []
        for row in reader:
            p1 = np.array(nodes[row["node1id"]])/shape[0]
            p2 = np.array(nodes[row["node2id"]])/shape[0]
            radius = float(row["avgRadiusAvg"])+radius_scale_factor/shape[0]
            forest.append({"node1": p1, "node2": p2, "radius": radius})
    img, _ = rasterize_forest(forest, 16, colorize=colorize, thresholds=thresholds)
    return img


def generate_image_from_graph_json(
        graph_json: pd.DataFrame,
        edges_df: pd.DataFrame,
        radius_interval: tuple[float] = (0, np.inf),
        dim: int=1216,
        image_size_mm: float=3,
        colorize: Literal["continuous", "thresholds", "random", "white"] = "white",
        color_thresholds: list[float] = None,
        radius_correction_factor: float = -1.0
    ) -> np.ndarray:
    """
    Generates an image from a graph JSON structure and edges DataFrame.
    Args:
        graph_json (pd.DataFrame): The graph JSON structure containing edges and their properties.
        edges_df (pd.DataFrame): DataFrame containing edge properties, including 'avgRadiusAvg'.
        radius_interval (tuple[float]): A tuple specifying the minimum and maximum radius for edges to be included in the image.
        dim (int): The dimension of the image (assumed square).
        image_size_mm (float): The size of the image in millimeters, used for scaling.
        colorize (Literal["continuous", "thresholds", "random", None]): Specifies how to color the edges.
            - "continuous": Color edges based on their radius, using a continuous color map.
            - "thresholds": Color edges based on the given thresholds.
            - "random": Assign a random color to each segment.
            - None: Use a default color (white).
        color_thresholds (list[float]): A list of thresholds for coloring edges when `colorize` is set to "thresholds". 
            This should be provided as a list of floats representing the thresholds for edge radii.
    Returns:
        np.ndarray: An image represented as a NumPy array of shape (dim, dim).
    """
    circles = list()
    radii = list()
    colors = list()
    colored_radius_add = .5/dim if colorize!="white" else 0 # Adjusted radius for colorized edges
    if colorize == "thresholds":
        if color_thresholds is None:
            raise ValueError("color_thresholds must be provided when colorize is 'thresholds'")
        intensities = np.linspace(0.1, 1, num=len(color_thresholds) + 1)
        thresholds = np.array([0, *color_thresholds, math.inf]) / image_size_mm
    for e in graph_json["graph"]["edges"]:
        if e["id"] in edges_df.index:
            # Correct the radius based on the correction factor
            edge_radius= (edges_df.loc[e["id"], "avgRadiusAvg"] + radius_correction_factor)/dim
            edge_radii = list()
            edge_pos = list()
            for v in e.get("skeletonVoxels", []):
                if math.isfinite(v["minDistToSurface"]):
                    radius = min(v["minDistToSurface"]/dim, edge_radius)
                    edge_radii.append(radius)
                    edge_pos.append((v["pos"][0]/dim, v["pos"][1]/dim))
            edge_median = np.median(edge_radii) if edge_radii else 0
            # Check if edge_median is within the specified radius interval
            if not (radius_interval[0] <= edge_median*image_size_mm <= radius_interval[1]):
                continue
            circles.extend([Circle(xy=(x, y), radius=r+colored_radius_add) for (x, y), r in zip(edge_pos, edge_radii)])
            radii.extend(edge_radii)
            if colorize == "random":
                color = np.random.rand(3)
                colors.extend([color] * len(edge_radii))
            elif colorize == "continuous":
                cont_colors = np.minimum(np.array(edge_radii) * image_size_mm / 0.015,1)
                colors.extend(cm.plasma(cont_colors))
            elif colorize == "thresholds":
                if color_thresholds is None:
                    raise ValueError("color_thresholds must be provided when colorize is 'thresholds'")
                c_new = np.zeros_like(edge_radii)
                for i in range(1, len(thresholds)):
                    c_new[(thresholds[i - 1] < edge_radii) & (edge_radii <= thresholds[i])] = intensities[i - 1]
                colors.extend(cm.plasma(c_new))
            elif colorize  == "white":
                # Default color (white)
                colors.extend([np.array([1, 1, 1, 1])] * len(edge_radii))
            else:
                raise ValueError(f"Unknown colorize option: {colorize}")
    # Sort circles, random_colors, and radii together by radius in descending order
    indices = sorted(range(len(radii)), key=lambda i: radii[i], reverse=True)
    circles = [circles[i] for i in indices]
    colors = [colors[i] for i in indices]
    radii = [radii[i] for i in indices]

    dpi=100
    x_inch = dim / dpi
    y_inch = dim / dpi
    figure = plt.figure(figsize=(x_inch,y_inch))
    figure.patch.set_facecolor('black')
    ax = plt.axes([0., 0., 1., 1.], frameon=False, xticks=[], yticks=[])
    ax.add_collection(collections.PatchCollection(circles, facecolors=colors, antialiaseds=True))
    figure.canvas.draw()
    data = np.frombuffer(figure.canvas.buffer_rgba(), dtype=np.uint8)
    image = data.reshape(figure.canvas.get_width_height()[::-1] + (4,))
    image = image[:, :, :3]
    if colorize == "white":
        image = image.max(axis=-1)  # Convert to grayscale
        image[image>0] = 255  # Convert to binary image
    plt.close(figure)
    return np.rot90(image, k=3)  # Rotate the image 90 degrees counter-clockwise
