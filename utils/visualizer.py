import numpy as np
import csv

from random import random


import math
from PIL import Image
from matplotlib import pyplot as plt, collections, cm

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

def node_edges_to_graph(nodes_file_path: str, edges_file_path: str, shape: tuple[int], colorize=False, radius_scale_factor=1, thresholds=None) -> np.ndarray:
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
            radius = float(row["avgRadiusAvg"])*radius_scale_factor/shape[0]
            forest.append({"node1": p1, "node2": p2, "radius": radius})
    img, _ = rasterize_forest(forest, 16, colorize=colorize, thresholds=thresholds)
    return img
