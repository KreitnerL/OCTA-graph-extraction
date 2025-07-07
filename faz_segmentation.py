import numpy as np
from PIL import Image
from skimage.morphology import skeletonize
from monai.transforms import KeepLargestConnectedComponent
from natsort import natsorted
import glob
from tqdm import tqdm
import os
from multiprocessing import cpu_count
import concurrent.futures
import cv2
from math import inf
import nibabel as nib

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

    img_inverted = (1-img/255).astype(np.float32)[np.newaxis,:,:]
    faz = KeepLargestConnectedComponent(connectivity=1)(img_inverted)[0].numpy()

    faz_larger_down = cv2.resize(faz, dsize=out_shape, interpolation=cv2.INTER_AREA)
    faz_larger: np.ndarray = cv2.resize(faz_larger_down, dsize=faz.shape, interpolation=cv2.INTER_LINEAR)
    faz_larger[faz_larger>0]=1

    img_merged = np.copy(img/255)
    img_merged[faz_larger==1]=np.maximum(img_merged[faz_larger==1],img_skel[faz_larger==1])
    img_merged[faz_larger<1] = 1

    img_inverted = (1-img_merged).astype(np.float32)[np.newaxis,:,:]
    faz_final = KeepLargestConnectedComponent(connectivity=1)(img_inverted)[0].numpy()
    return faz_final


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--source_files', help="Absolute path to the folder containing the DVC segmentation maps", type=str, required=True)
    parser.add_argument('--output_dir', help="Absolute path to the folder where the faz segmentation files wil be stored.", type=str, default=None)
    parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=-1)
    parser.add_argument('--num_samples', help="Maximum number of samples to process.", type=int, default=inf)
    args = parser.parse_args()

    data_files: list[str] = natsorted(glob.glob(args.source_files, recursive=True))
    source_folder = os.path.dirname(os.path.commonprefix(data_files))
    output_dir: str = args.output_dir

    def task(path: str):
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
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        Image.fromarray(img_and_faz.astype(np.uint8)).save(out_path)

    if args.threads == -1:
        # If no argument is provided, use all available threads but one
        cpus = cpu_count()
        threads = min(cpus-1 if cpus>1 else 1,args.num_samples)
    else:
        threads=args.threads

    if threads>1:
        # Multi processing
        with tqdm(total=min(args.num_samples, len(data_files)), desc="Segmenting FAZ...") as pbar:
            with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
                future_dict = {executor.submit(task, data_files[i]): i for i in range(len(data_files))}
                for future in concurrent.futures.as_completed(future_dict):
                    i = future_dict[future]
                    pbar.update(1)
    else:
        if data_files[0].endswith(".nii.gz"):
            print("Warning: 3D volumes are not recommended for FAZ segmentation! For optimal results use 2D segmentations instead!")
        for path in tqdm(data_files, desc="Segmenting FAZ..."):
            task(path)

    
