import math

import numpy as np
from scipy import ndimage


def get_angle(x1, y1, x2, y2):
    angle = math.atan2(y2 - y1, x2 - x1) * 180 / math.pi
    return angle

def get_ETDRS_grid_indices(center_index, radius: float=1216/6, radius_2: float=1216/6 * 2.5):
    x, y = center_index
    r = math.ceil(radius)
    y_indices, x_indices = np.mgrid[-r:r+1, -r:r+1]
    dist = ((x_indices+.5)**2 + (y_indices+.5)**2) / radius**2
    center_mask = dist <= 1

    x_i = np.rint(x+x_indices).astype(np.uint16)
    y_i = np.rint(y+y_indices).astype(np.uint16)

    center_indices = x_i[center_mask], y_i[center_mask]

    r = math.ceil(radius_2)
    y_indices, x_indices = np.mgrid[-r:r+1, -r:r+1]
    dist = ((x_indices+.5)**2 + (y_indices+.5)**2) / radius_2**2
    inner_mask = (dist>(radius**2)/(radius_2**2)) & (dist <= 1)

    x_indices = x_indices[inner_mask]
    y_indices = y_indices[inner_mask]

    #degrees = np.degrees(np.arccos((x_indices+.5)/radius_2/dist[inner_mask]))
    degrees = np.arctan2(y_indices, x_indices) * 180 / np.pi
    q1_mask = 135<abs(degrees)
    q2_mask = (-45>degrees) & (-135<=degrees)
    q3_mask = abs(degrees)<45
    q4_mask = (45<degrees) & (degrees<=135)

    x_i = np.rint(x+x_indices).astype(np.uint16)
    y_i = np.rint(y+y_indices).astype(np.uint16)

    q1_indices = x_i[q1_mask], y_i[q1_mask]
    q2_indices = x_i[q2_mask], y_i[q2_mask]
    q3_indices = x_i[q3_mask], y_i[q3_mask]
    q4_indices = x_i[q4_mask], y_i[q4_mask]

    return center_indices, q1_indices, q2_indices, q3_indices, q4_indices

def get_ETDRS_grid_masks(faz: np.ndarray, center_radius=1216/6, inner_radius=1216/6 * 2.5) -> tuple[np.ndarray]:
    center = [int(i) for i in ndimage.center_of_mass(faz)]
    
    center_indices, q1_indices, q2_indices, q3_indices, q4_indices = get_ETDRS_grid_indices(center, center_radius, inner_radius)

    center_mask = np.zeros_like(faz, dtype=np.bool_)
    center_mask[center_indices[0], center_indices[1]] = True

    q1_mask = np.zeros_like(faz, dtype=np.bool_)
    q1_mask[q1_indices[0], q1_indices[1]] = True

    q2_mask = np.zeros_like(faz, dtype=np.bool_)
    q2_mask[q2_indices[0], q2_indices[1]] = True

    q3_mask = np.zeros_like(faz, dtype=np.bool_)
    q3_mask[q3_indices[0], q3_indices[1]] = True

    q4_mask = np.zeros_like(faz, dtype=np.bool_)
    q4_mask[q4_indices[0], q4_indices[1]] = True

    return center_mask, q1_mask, q2_mask, q3_mask, q4_mask
