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

source_dir = "/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/ves_seg/Sjögren"
data_files = natsorted(glob.glob(source_dir+'/*DVC*.png', recursive=True))
output_dir = "/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/faz_seg/Sjögren"
for path in tqdm(data_files):
    name = path.split("/")[-1]
    if not "DVC" in name:
        continue

    img_orig = np.array(Image.open(path))
    img = np.copy(img_orig)
    BORDER = 200
    img[:BORDER] = img[-BORDER:] = img[:,:BORDER]= img[:,-BORDER:] = 255

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


    # img_and_faz = np.copy(img_orig)
    # img_and_faz[(faz_final==1) & (img_and_faz==0)]=127
    # Image.fromarray(img_and_faz.astype(np.uint8)).save(path)

    img_and_faz = np.zeros_like(img)
    img_and_faz[(faz_final==1) & (img_and_faz==0)]=255
    Image.fromarray(img_and_faz.astype(np.uint8)).save(path.replace(source_dir, output_dir).replace("pred", "faz_pred"))