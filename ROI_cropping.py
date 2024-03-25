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

"""
This script is used to crop the ROI from the images. It is assumed that the ROI is located in the center of the image.
If the image is larger than the specified ROI size, the script will try to find the ROI by looking for the
largest difference in pixel values between the ROI and the surrounding area. The script will then crop the image to the roi_size
around the found ROI. If the image is smaller than the roi_size, the script will pad the image with zeros to reach the target size.
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--input_dir', type=str, required=True)
    parser.add_argument('--output_dir', type=str, required=True)
    parser.add_argument('--roi_size', type=int, default=512)
    parser.add_argument('--image_size', type=int, default=768)
    parser.add_argument('--problem_threshold', type=float, default=0.15)


    args = parser.parse_args()
    roi_size = args.roi_size
    image_size = args.image_size

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
        try:
            img = np.array(Image.open(path).convert("L")).astype(np.float32)
        except OSError:
            problematic.append({
                "path": path,
                "save_path": None,
                "shape": None,
                "xs": None,
                "ys": None
            })
            continue
        
        if img.shape[0] > roi_size+1 and img.shape[1] > roi_size+1:
            diff_xx = (img[:image_size//3, image_size//3:image_size//3*2] - img[1:image_size//3+1,image_size//3:image_size//3*2]).sum(axis=1)
            diff_xy = abs(img[:image_size//3, image_size//3:image_size//3*2] - img[:image_size//3,image_size//3+1:image_size//3*2+1]).sum(axis=1)
            xxs = np.argmax(diff_xx)+1
            xys = np.argmin(diff_xy[:-1]-diff_xy[1:])+1

            diff_yx = abs(img[image_size//3:image_size//3*2,:image_size//3] - img[image_size//3+1:image_size//3*2+1,:image_size//3]).sum(axis=0)
            diff_yy = (img[image_size//3:image_size//3*2,:image_size//3] - img[image_size//3:image_size//3*2,1:image_size//3+1]).sum(axis=0)
            yxs = np.argmin(diff_yx[:-1]-diff_yx[1:])+1
            yys = np.argmax(diff_yy)+1

            img_flip = np.flip(np.flip(img, axis=0), axis=1)
            diff_xx_reverse = (img_flip[:image_size//3,image_size//3:image_size//3*2] - img_flip[1:image_size//3+1,image_size//3:image_size//3*2]).sum(axis=1)
            diff_xy_reverse = abs(img_flip[:image_size//3,image_size//3:image_size//3*2] - img_flip[:image_size//3,image_size//3+1:image_size//3*2+1]).sum(axis=1)
            xxs_reverse = image_size-(np.argmax(diff_xx_reverse)+1)-roi_size
            xys_reverse = image_size-(np.argmin(diff_xy_reverse[:-1]-diff_xy_reverse[1:])+1)-roi_size
            
            diff_yy_reverse = (img_flip[image_size//3:image_size//3*2,:image_size//3] - img_flip[image_size//3:image_size//3*2,1:image_size//3+1]).sum(axis=0)
            diff_yx_reverse = abs(img_flip[image_size//3:image_size//3*2,:image_size//3] - img_flip[image_size//3+1:image_size//3*2+1,:image_size//3]).sum(axis=0)
            yxs_reverse = image_size-(np.argmin(diff_yx_reverse[:-1]-diff_yx_reverse[1:])+1)-roi_size
            yys_reverse = image_size-(np.argmax(diff_yy_reverse)+1)-roi_size

            xs_list = [xxs,xys,xxs_reverse,xys_reverse]
            xs = max(set(xs_list), key=xs_list.count)
            ys_list = [yxs,yys,yxs_reverse,yys_reverse]
            ys = max(set(ys_list), key=ys_list.count)

            img_cropped = img[xs:xs+roi_size,ys:ys+roi_size].astype(np.uint8)
        else:
            img_cropped = img[:roi_size,:roi_size].astype(np.uint8)

        if not os.path.exists(f"{args.output_dir}/{cohort}"):
            os.makedirs(f"{args.output_dir}/{cohort}")
        save_path = f"{args.output_dir}/{cohort}/{name}"
        
        if (img_cropped.shape[0] != roi_size or img_cropped.shape[1] != roi_size) or (xs<args.problem_threshold*image_size) or (ys > (1-args.problem_threshold)*image_size):
            if (img_cropped.shape[0] != roi_size or img_cropped.shape[1] != roi_size) and path:
                problematic.append({
                    "path": path,
                    "save_path": save_path,
                    "shape": (img_cropped.shape[0],img_cropped.shape[1]),
                    "xs": xs,
                    "ys": ys
                })
        img_cropped_save = np.zeros((roi_size,roi_size)).astype(np.uint8)
        img_cropped_save[:img_cropped.shape[0],:img_cropped.shape[1]] = img_cropped[:roi_size,:roi_size]
        img_cropped = img_cropped_save

        Image.fromarray(img_cropped).save(save_path)


    with open(f"{args.output_dir}/problematic.csv", 'w+') as csvfile:
        writer = csv.writer(csvfile)
        if len(problematic)>0:
            writer.writerow(list(problematic[0].keys()))
            for entry in problematic:
                writer.writerow(entry.values())
        else:
            writer.writerow(["ALL CLEAR"])
    