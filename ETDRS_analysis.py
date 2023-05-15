import glob
from natsort import natsorted
from tqdm import tqdm
import pandas
from numpy import nan
import numpy as np
from PIL import Image

d = dict()
scaling_factor = 3000.0 / 1216

base_path = "/home/linus/Datasets/OCTA_analysis/OCTA_TUMNeuro_initial/"

with open("/home/linus/Datasets/OCTA/processed/OCTA_TUMNeuro_initial/valid.txt") as f:
    valid_code_names = [n.removesuffix("\n") for n in f.readlines()]

with open("/home/linus/Datasets/OCTA/processed/OCTA_TUMNeuro_initial/invalid.txt") as f:
    invalid_code_names = [n.removesuffix("\n") for n in f.readlines()]

data_files = natsorted(glob.glob(base_path+'faz_seg/**/*.png'))

for data_file in tqdm(data_files):
    faz = np.array(Image.open(data_file))
    faz_volume = (faz/255).sum()/1216**2 * 3

    group, image_ID = data_file.removeprefix(base_path+"faz_seg/").split("/")
    image_ID = image_ID.removeprefix("faz_pred_").removesuffix(".png")
    code_name = image_ID.replace(" - Kopie", "").replace(" ", "_").removesuffix("_OCTA")
    if not code_name in d:
        dd = dict()
        dd["Image_ID"] = image_ID
        dd["Group"] = group
        dd["Eye"] = "OD" if "OD" in image_ID else "OS"
        dd["Layer"] = "SVC" if "SVC" in image_ID else "DVC"

        if code_name in valid_code_names:
            dd["Quality Control"] = "OK" 
        elif code_name in invalid_code_names:
            dd["Quality Control"] = "FAIL"
        else:
            dd["Quality Control"] = "NOT_FOUND"
        dd["FAZ area"] = faz_volume
        
        dd["C0 Density (diameter < 10um)"] = nan
        dd["C0 Density (10um < diameter < 20um)"] = nan
        dd["C0 Density (20um < diameter < 30um)"] = nan
        dd["C0 Density (diameter > 30um)"] = nan

        dd["S1 Density (diameter < 10um)"] = nan
        dd["S1 Density (10um < diameter < 20um)"] = nan
        dd["S1 Density (20um < diameter < 30um)"] = nan
        dd["S1 Density (diameter > 30um)"] = nan

        dd["N1 Density (diameter < 10um)"] = nan
        dd["N1 Density (10um < diameter < 20um)"] = nan
        dd["N1 Density (20um < diameter < 30um)"] = nan
        dd["N1 Density (diameter > 30um)"] = nan

        dd["I1 Density (diameter < 10um)"] = nan
        dd["I1 Density (10um < diameter < 20um)"] = nan
        dd["I1 Density (20um < diameter < 30um)"] = nan
        dd["I1 Density (diameter > 30um)"] = nan

        dd["T1 Density (diameter < 10um)"] = nan
        dd["T1 Density (10um < diameter < 20um)"] = nan
        dd["T1 Density (20um < diameter < 30um)"] = nan
        dd["T1 Density (diameter > 30um)"] = nan

        d[code_name] = dd

data_files = natsorted(glob.glob(base_path+'graph_features/**/**/*_edges.csv'))

for data_file in tqdm(data_files):

    df = pandas.read_csv(data_file, sep=';')
    df = df[(df.volume > 0) & (df.curveness >= 1.0)]
    dd = dict()

    group, image_ID, name = data_file.removeprefix(base_path+'graph_features/').split("/")
    image_ID = image_ID.removeprefix("pred_")


    if "C0" in name:
        area = "C0"
        area_factor = 0.000873
    elif "S1" in name:
        area = "S1"
        area_factor = 0.001145
    elif "N1" in name:
        area = "N1"
        area_factor = 0.001145
    elif "I1" in name:
        area = "I1"
        area_factor = 0.001145
    elif "T1" in name:
        area = "T1"
        area_factor = 0.001145


    code_name = image_ID.replace(" - Kopie", "").replace(" ", "_").removesuffix("_OCTA")
    if not code_name in d:
        dd = dict()
        dd["Image_ID"] = image_ID
        dd["Group"] = group
        dd["Eye"] = "OD" if "OD" in image_ID else "OS"
        dd["Layer"] = "SVC" if "SVC" in image_ID else "DVC"

        if code_name in valid_code_names:
            dd["Quality Control"] = "OK" 
        elif code_name in invalid_code_names:
            dd["Quality Control"] = "FAIL"
        else:
            dd["Quality Control"] = "NOT_FOUND"

        if code_name.replace("SVC", "DVC") in d:
            dd["FAZ area"] = d[code_name.replace("SVC", "DVC")]["FAZ area"]
        else:
            dd["FAZ area"] = nan
        
        dd["C0 Density (diameter < 10um)"] = nan
        dd["C0 Density (10um < diameter < 20um)"] = nan
        dd["C0 Density (20um < diameter < 30um)"] = nan
        dd["C0 Density (diameter > 30um)"] = nan

        dd["S1 Density (diameter < 10um)"] = nan
        dd["S1 Density (10um < diameter < 20um)"] = nan
        dd["S1 Density (20um < diameter < 30um)"] = nan
        dd["S1 Density (diameter > 30um)"] = nan

        dd["N1 Density (diameter < 10um)"] = nan
        dd["N1 Density (10um < diameter < 20um)"] = nan
        dd["N1 Density (20um < diameter < 30um)"] = nan
        dd["N1 Density (diameter > 30um)"] = nan

        dd["I1 Density (diameter < 10um)"] = nan
        dd["I1 Density (10um < diameter < 20um)"] = nan
        dd["I1 Density (20um < diameter < 30um)"] = nan
        dd["I1 Density (diameter > 30um)"] = nan

        dd["T1 Density (diameter < 10um)"] = nan
        dd["T1 Density (10um < diameter < 20um)"] = nan
        dd["T1 Density (20um < diameter < 30um)"] = nan
        dd["T1 Density (diameter > 30um)"] = nan

        d[code_name] = dd

    density_smallest = df[df.avgRadiusAvg * scaling_factor < 5.0].volume.sum() * area_factor
    density_small = df[(df.avgRadiusAvg * scaling_factor > 5.0) & (df.avgRadiusAvg * scaling_factor < 10.0)].volume.sum() * area_factor
    density_large = df[(df.avgRadiusAvg * scaling_factor > 10.0) & (df.avgRadiusAvg * scaling_factor < 15.0)].volume.sum() * area_factor
    density_largest = df[df.avgRadiusAvg * scaling_factor > 15.0].volume.sum() * area_factor

    d[code_name][area + " Density (diameter < 10um)"] = density_smallest
    d[code_name][area + " Density (10um < diameter < 20um)"] = density_small
    d[code_name][area + " Density (20um < diameter < 30um)"] = density_large
    d[code_name][area + " Density (diameter > 30um)"] = density_largest


df = pandas.DataFrame(d.values())

df.to_csv(base_path+'/density_measurements_v2.csv', index=False, sep=";")
