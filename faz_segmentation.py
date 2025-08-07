import concurrent.futures
import glob
import os
from functools import partial
from math import inf
from multiprocessing import cpu_count

import cv2
import nibabel as nib
import numpy as np
from natsort import natsorted
from PIL import Image
from scipy import ndimage
from skimage.morphology import skeletonize
from tqdm import tqdm


def keep_largest_connected_component(image: np.ndarray) -> np.ndarray:
    """
    Keeps only the largest 4-connected component in a binary 2D image.
    Parameters:
        image (np.ndarray): 2D binary image. Non-zero pixels are treated as foreground.
    Returns:
        image (np.ndarray): Binary image of same shape and dtype with only the largest connected component.
    """
    if image.ndim != 2:
        raise ValueError("Input must be a 2D array.")
    
    labeled, num_features = ndimage.label(image)  # 4-connectivity
    if labeled.max() == 0:
        return np.zeros_like(image, dtype=image.dtype)

    counts = np.bincount(labeled.ravel())[1:]  # exclude background (label 0)
    largest_label = np.argmax(counts) + 1
    output = (labeled == largest_label).astype(image.dtype)
    return output

def get_faz_mask_robust(img_orig: np.ndarray) -> np.ndarray:
    for border in [600,500,400,300,200, 100]:
        faz = get_faz_mask(img_orig, border)
        if (faz[border+1,:]).any() or (faz[-border-1,:]).any() or (faz[:,border+1]).any() or (faz[:, -border-1]).any():
            continue
        return faz
    return faz

def get_faz_mask(img_orig: np.ndarray, BORDER=200) -> np.ndarray:
    img = np.copy(img_orig)
    img[:BORDER] = img[-BORDER:] = img[:,:BORDER]= img[:,-BORDER:] = 255

    # TODO
    scale_factor=.16
    out_shape = [int(scale_factor * d) for d in img.shape[-2:]]
    img_fuzzy_down = cv2.resize(img/255, dsize=out_shape, interpolation=cv2.INTER_AREA)
    img_fuzzy: np.ndarray = cv2.resize(img_fuzzy_down, dsize=img.shape, interpolation=cv2.INTER_LINEAR)

    img_fuzzy[img_fuzzy>0]=1

    img_skel = skeletonize(img_fuzzy,method = 'zhang')

    img_inverted = (1-img/255).astype(np.float32)[:,:]
    faz = keep_largest_connected_component(img_inverted)

    faz_larger_down = cv2.resize(faz, dsize=out_shape, interpolation=cv2.INTER_AREA)
    faz_larger: np.ndarray = cv2.resize(faz_larger_down, dsize=faz.shape, interpolation=cv2.INTER_LINEAR)
    faz_larger[faz_larger>0]=1

    img_merged = np.copy(img/255)
    img_merged[faz_larger==1]=np.maximum(img_merged[faz_larger==1],img_skel[faz_larger==1])
    img_merged[faz_larger<1] = 1

    img_inverted = (1-img_merged).astype(np.float32)[:,:]
    faz_final = keep_largest_connected_component(img_inverted)
    return faz_final

def task(path: str, source_folder: str, output_dir: str):
    name = path.split("/")[-1]
    if path.endswith(".nii.gz"):
        nifti: nib.Nifti1Image = nib.load(path)
        image_3d = nifti.get_fdata()
        img_orig = np.max(image_3d, axis=-1)
        path = path.replace(".nii.gz", ".png")
    else:
        img_orig = np.array(Image.open(path))
    faz_final = get_faz_mask_robust(img_orig)

    img_and_faz = np.zeros_like(img_orig)
    img_and_faz[(faz_final==1) & (img_and_faz==0)]=255
    out_path = path.replace(source_folder, output_dir).replace(name, "faz_"+name)
    out_dir = "/".join(out_path.split("/")[:-1])
    
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(img_and_faz.astype(np.uint8)).save(out_path)

def perform_faz_segmentation(source_files: str, output_dir: str, threads: int = -1, num_samples: int = inf):
    data_files: list[str] = natsorted(glob.glob(source_files, recursive=True))
    source_folder = os.path.dirname(os.path.commonprefix(data_files))

    if threads>1:
        # Multi processing
        with tqdm(total=min(num_samples, len(data_files)), desc="Segmenting FAZ...") as pbar:
            with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
                future_dict = {executor.submit(partial(task, source_folder=source_folder, output_dir=output_dir), data_files[i]): i for i in range(len(data_files))}
                for _ in concurrent.futures.as_completed(future_dict):
                    pbar.update(1)
    else:
        if data_files[0].endswith(".nii.gz"):
            print("Warning: 3D volumes are not recommended for FAZ segmentation! For optimal results use 2D segmentations instead!")
        for path in tqdm(data_files, desc="Segmenting FAZ..."):
            task(path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--source_files', help="Absolute path to the folder containing the DVC segmentation maps", type=str, required=True)
    parser.add_argument('--output_dir', help="Absolute path to the folder where the faz segmentation files wil be stored.", type=str, default=None)
    parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=max(1,cpu_count()-1))
    parser.add_argument('--num_samples', help="Maximum number of samples to process.", type=int, default=inf)
    args = parser.parse_args()

    perform_faz_segmentation(args.source_files, args.output_dir, threads=args.threads, num_samples=args.num_samples)
