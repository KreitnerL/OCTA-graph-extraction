from PIL import Image
import numpy as np
from natsort import natsorted
import glob
from tqdm import tqdm
import os
from utils.ETDRS_grid import get_ETDRS_grid_indices
from scipy import ndimage
from graph_feature_extractor import extract_graph_features

def get_code_name(filename: str) -> str:
    return filename.removeprefix("faz_").removeprefix("pred_").replace(" - Kopie", "").replace(" ", "_").removesuffix("_OCTA.png").removesuffix(".png")

ves_seg_input_dir = "/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/ves_seg/Sjögren/"
outdir = "/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/graph_features/Sjögren/"

ves_seg_files = natsorted(glob.glob('/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/ves_seg/Sjögren/*.png', recursive=True))
faz_seg_files = natsorted(glob.glob('/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/faz_seg/Sjögren/*.png', recursive=True))

dvc_faz_code_name_map = {get_code_name(path.split("/")[-1]): path for path in faz_seg_files if "DVC" in path}

for ves_seg_path in tqdm(ves_seg_files):
    print("INFO --- " + ves_seg_path)
    faz_code_name = get_code_name(ves_seg_path.split("/")[-1]).replace("SVC", "DVC")
    if faz_code_name not in dvc_faz_code_name_map:
        continue
    
    name = ves_seg_path.split("/")[-1]
    ves_seg_img_parent_dir = ves_seg_path.removesuffix(name)
    ves_seg = np.array(Image.open(ves_seg_path))
    faz_seg = np.array(Image.open(dvc_faz_code_name_map[faz_code_name]))

    center = ndimage.center_of_mass(faz_seg)

    ETDRS_grid_indices = get_ETDRS_grid_indices(center)
    if "OS" in faz_code_name:
        suffixes = ["C0", "S1", "N1", "I1", "T1"]
    else:
        suffixes = ["C0", "S1", "T1", "I1", "N1"]

    save_dir = ves_seg_path.replace(ves_seg_input_dir, outdir).removesuffix(".png")
    os.mkdir(save_dir)

    for indices, suffix in zip(ETDRS_grid_indices, suffixes):
        mask = np.zeros_like(faz_seg, dtype=np.bool8)
        try:
            mask[indices] = True
        except IndexError:
            continue

        ves_seg_masked = np.copy(ves_seg)
        ves_seg_masked[~mask] = 0

        # Compute graph
        extract_graph_features(ves_seg_masked, name.replace(".png", "_"+suffix+".png"), save_dir)
