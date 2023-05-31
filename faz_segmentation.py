import numpy as np
from PIL import Image
import torch
from torch.nn.functional import interpolate
from skimage.morphology import skeletonize
from monai.transforms import KeepLargestConnectedComponent
from natsort import natsorted
import glob
from tqdm import tqdm
import numpy as np
import os

def get_faz_mask_robust(img_orig: np.ndarray) -> np.ndarray:
    for border in [600,500,400,300,200]:
        faz = get_faz_mask(img_orig, border)
        if (faz[border+1,:]).any() or (faz[-border-1,:]).any() or (faz[:,border+1]).any() or (faz[:, -border-1]).any():
            continue
        return faz

def get_faz_mask(img_orig: np.ndarray, BORDER=200) -> np.ndarray:
    img = np.copy(img_orig)
    img[:BORDER] = img[-BORDER:] = img[:,:BORDER]= img[:,-BORDER:] = 255

    # TODO
    img_fuzzy_down = interpolate(
        torch.tensor(img[np.newaxis,np.newaxis,:,:]/255, dtype=torch.float32),
        scale_factor=.16, mode="area")
    img_fuzzy = interpolate(
        img_fuzzy_down,
        size=img.shape, mode="bilinear").squeeze()

    img_fuzzy[img_fuzzy>0]=1

    img_skel = skeletonize(img_fuzzy.numpy(),method = 'zhang')

    img_inverted = (1-img/255).astype(np.float32)[np.newaxis,:,:]
    faz = KeepLargestConnectedComponent(connectivity=1)(img_inverted)[0].numpy()

    faz_larger_down = interpolate(
        torch.tensor(faz[np.newaxis,np.newaxis,:,:], dtype=torch.float32),
        scale_factor=.16, mode="area")
    faz_larger = interpolate(
        faz_larger_down,
        size=faz.shape, mode="bilinear").squeeze()
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
    parser.add_argument('--source_dir', help="Absolute path to the folder containing all the segmentation maps", type=str, required=True)
    parser.add_argument('--source_files', help="Absolute path to the folder containing all the segmentation maps", type=str, default="/*.png")
    parser.add_argument('--output_dir', help="Absolute path to the folder where the faz segmentation files wil be stored.", type=str, default=None)
    parser.add_argument('--threads', help="Absolute path to the folder where the faz segmentation files wil be stored.", type=int, default=1)
    args = parser.parse_args()

    data_files: list[str] = natsorted(glob.glob(args.source_dir + args.source_files, recursive=True))
    output_dir: str = args.output_dir

    def task(path: str):
        name = path.split("/")[-1]
        img_orig = np.array(Image.open(path))
        faz_final = get_faz_mask_robust(img_orig)

        # img_and_faz = np.copy(img_orig)
        # img_and_faz[(faz_final==1) & (img_and_faz==0)]=127
        # Image.fromarray(img_and_faz.astype(np.uint8)).save(path)

        img_and_faz = np.zeros_like(img_orig)
        img_and_faz[(faz_final==1) & (img_and_faz==0)]=255
        out_path = path.replace(args.source_dir, output_dir).replace(name, "faz_"+name)
        out_dir = "/".join(out_path.split("/")[:-1])
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        Image.fromarray(img_and_faz.astype(np.uint8)).save(out_path)

    from multiprocessing.dummy import Pool as Pool
    from multiprocessing.pool import ThreadPool
    pool: ThreadPool = Pool(args.threads)
    results = list(tqdm(pool.imap(task, data_files), total=len(data_files)))

    
