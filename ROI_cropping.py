from PIL import Image
import numpy as np
from natsort import natsorted
import glob
from tqdm import tqdm
import os
import csv
import warnings
import argparse
warnings.filterwarnings('error')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--input_dir', type=str, required=True)
    parser.add_argument('--output_dir', type=str, required=True)

    args = parser.parse_args()

    data_files = natsorted(glob.glob(f'{args.input_dir}/**/*.png', recursive=True))
    assert len(data_files)>0, f"No input files found for path {args.input_dir}"

    problematic = []
    std_outs = []
    std_ins = []
    for path in tqdm(data_files):
        if not os.path.isfile(path):
            continue
        name = path.split("/")[-1].replace(".PNG", ".png")
        cohort = path.split("/")[-2]
        img = np.array(Image.open(path).convert("L")).astype(np.float32)
        
        diff_xx = (img[0:256, 256:512] - img[1:257,256:512]).sum(axis=1)
        diff_xy = abs(img[0:256, 256:512] - img[0:256,257:513]).sum(axis=1)
        xxs = np.argmax(diff_xx)+1
        xys = np.argmin(diff_xy[:-1]-diff_xy[1:])+1

        diff_yx = abs(img[256:512,0:256] - img[257:513,0:256]).sum(axis=0)
        diff_yy = (img[256:512,0:256] - img[256:512,1:257]).sum(axis=0)
        yxs = np.argmin(diff_yx[:-1]-diff_yx[1:])+1
        yys = np.argmax(diff_yy)+1

        img_flip = np.flip(np.flip(img, axis=0), axis=1)
        diff_xx_reverse = (img_flip[0:256,256:512] - img_flip[1:257,256:512]).sum(axis=1)
        diff_xy_reverse = abs(img_flip[0:256,256:512] - img_flip[0:256,257:513]).sum(axis=1)
        xxs_reverse = 768-(np.argmax(diff_xx_reverse)+1)-512
        xys_reverse = 768-(np.argmin(diff_xy_reverse[:-1]-diff_xy_reverse[1:])+1)-512
        
        diff_yy_reverse = (img_flip[256:512,0:256] - img_flip[256:512,1:257]).sum(axis=0)
        diff_yx_reverse = abs(img_flip[256:512,0:256] - img_flip[257:513,0:256]).sum(axis=0)
        yxs_reverse = 768-(np.argmin(diff_yx_reverse[:-1]-diff_yx_reverse[1:])+1)-512
        yys_reverse = 768-(np.argmax(diff_yy_reverse)+1)-512

        xs_list = [xxs,xys,xxs_reverse,xys_reverse]
        xs = max(set(xs_list), key=xs_list.count)
        ys_list = [yxs,yys,yxs_reverse,yys_reverse]
        ys = max(set(ys_list), key=ys_list.count)

        img_cropped = img[xs:xs+512,ys:ys+512].astype(np.uint8)

        if not os.path.exists(f"{args.output_dir}/{cohort}"):
            os.makedirs(f"{args.output_dir}/{cohort}")
        save_path = f"{args.output_dir}/{cohort}/{name}"
        Image.fromarray(img_cropped).save(save_path)

        
        if (img_cropped.shape[0] != 512 or img_cropped.shape[1] != 512) or (xs<110) or (ys > img.shape[1]-100):
            if (img_cropped.shape[0] != 512 or img_cropped.shape[1] != 512) and path:
                problematic.append({
                    "path": path,
                    "save_path": save_path,
                    "shape": (img_cropped.shape[0],img_cropped.shape[1]),
                    "xs": xs,
                    "ys": ys
                })


    with open(f"{args.output_dir}/problematic.csv", 'w+') as csvfile:
        writer = csv.writer(csvfile)
        if len(problematic)>0:
            writer.writerow(list(problematic[0].keys()))
            for entry in problematic:
                writer.writerow(entry.values())
        else:
            writer.writerow(["ALL CLEAR"])
    