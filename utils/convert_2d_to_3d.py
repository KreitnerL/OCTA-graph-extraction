import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.morphology import skeletonize

def convert_2d_to_3d(ves_seg: np.ndarray, z_dim: int) -> np.ndarray:
    """
    Vectorized version of convert_2d_to_3d for better performance.
    
    Args:
        ves_seg (np.ndarray): 2D vessel segmentation mask.
        z_dim (int): Depth dimension for the 3D volume.
        
    Returns:
        np.ndarray: 3D vessel segmentation mask.
    """
    image_dist = distance_transform_edt(ves_seg)
    skeleton = skeletonize(ves_seg, method='lee')
    dist_skeleton = image_dist * skeleton
    
    # Get coordinates and radii of all skeleton points
    coords = np.argwhere(dist_skeleton > 0)
    if len(coords) == 0:
        return np.zeros((ves_seg.shape[0], ves_seg.shape[1], z_dim), dtype=np.uint8)
    
    radii = dist_skeleton[coords[:, 0], coords[:, 1]]
    
    # Create the 3D volume (height, width, depth)
    image_vol = np.zeros((ves_seg.shape[0], ves_seg.shape[1], z_dim), dtype=np.uint8)
    
    # Fixed z-center for all spheres
    z_center = z_dim // 2
    
    # For each skeleton point, compute which voxels fall within its sphere
    for i, (y_center, x_center) in enumerate(coords):
        radius = radii[i]
        
        # Define bounding box to limit computation
        y_min = max(0, int(y_center - radius))
        y_max = min(ves_seg.shape[0], int(y_center + radius + 1))
        x_min = max(0, int(x_center - radius))
        x_max = min(ves_seg.shape[1], int(x_center + radius + 1))
        z_min = max(0, int(z_center - radius))
        z_max = min(z_dim, int(z_center + radius + 1))
        
        # Create coordinate grids only for the bounding box
        y_local, x_local, z_local = np.meshgrid(
            np.arange(y_min, y_max),
            np.arange(x_min, x_max),
            np.arange(z_min, z_max),
            indexing='ij'
        )
        
        # Compute squared distances
        dist_sq = ((y_local - y_center) ** 2 + 
                   (x_local - x_center) ** 2 + 
                   (z_local - z_center) ** 2)
        
        # Set voxels within radius to 255
        mask = dist_sq < radius ** 2
        image_vol[y_min:y_max, x_min:x_max, z_min:z_max][mask] = 255
    
    return image_vol
