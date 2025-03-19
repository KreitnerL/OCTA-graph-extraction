import glob
from natsort import natsorted
from tqdm import tqdm
import pandas
from numpy import nan
import numpy as np
from PIL import Image
import os
from natsort import natsort_keygen
from math import pi

from utils.ETDRS_grid import get_ETDRS_grid_masks

def remove_plexus_code(name: str):
    return name.replace("_DCP", "").replace("_dcp", "").replace("_DVC", "").replace("_dvc", "").replace("_SCP", "").replace("_scp", "").replace("_SVC", "").replace("_svc", "")

def remove_eye_code(name: str):
     return name.replace("_OS", "").replace("_OD", "")

def remove_extentions(basename: str):
    return basename.replace(" .", ".").removesuffix(".png").removesuffix("_edges.csv").removesuffix("_full")

def code_name(path: str):
    return remove_plexus_code(remove_extentions(os.path.basename(path))).removeprefix("faz_").removeprefix("model_").removeprefix("model_").replace(" OCTA", "").replace(" ", "_").replace("__", "_")
    
def sanity_filter(df: pandas.DataFrame):
    return (df.volume > 0) & (df.distance > 0) & (df.curveness > 0) & (df.avgRadiusAvg > 0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--source_dir', type=str, help="Absolute path to the folder graph features", required=True)
    parser.add_argument('--output_dir', type=str, help="Absolute path to the output folder. If none is given, save in source folder.")
    parser.add_argument('--faz_files', type=str, help="Absolute path to the faz segmentation files. Required for etdrs analysis.")

    parser.add_argument('--radius_thresholds', type=str, default=None, help="Comma separated list of thresholds for vessel stratification [um].")
    parser.add_argument('--from_3d', action="store_true", help="Set this flag if your vessel segmentation was given in 3D")

    parser.add_argument('--mm', type=float, default=3.0, help="Height of the segmentation volume in mm. Default is 3 mm")
    parser.add_argument('--radius_correction_factor', type=float, default=1.3, help="Correction factor to scale the extracted radii with. Vessels in OCTA images appear larger than they really are. If you used our tool for vesser segementation, use the default value of 1.3")
    parser.add_argument('--etdrs', action="store_true", help="If set, use ETDRS grid stratification")
    parser.add_argument('--center_radius', type=float, default=3/6, help="Radius of ETDRS center radius in mm")
    parser.add_argument('--inner_radius', type=float, default=3/2.4, help="Radius of ETDRS center radius in mm")
    args = parser.parse_args()

    data_files: list[str] = natsorted(glob.glob(os.path.join(args.source_dir, "**/*_edges.csv"), recursive=True))
    assert len(data_files)>0, f"No '_edges.csv' files found in folder {args.source_dir}!"

    faz_map=dict()
    if args.faz_files:
        faz_files: list[str] = natsorted(glob.glob(args.faz_files, recursive=True))
        if len(data_files)==0:
            print(f"No files found in faz folder {args.faz_files}!")
        
        for faz_file in tqdm(faz_files):
            faz = np.array(Image.open(faz_file))
            image_area = faz.shape[0]*faz.shape[1]
            faz_area = (faz/255).sum()/image_area * args.mm**2

            faz_map[code_name(faz_file)] = faz_area

    if args.etdrs:
        assert faz_map, "FAZ files are required for ETDRS analysis!"
        # We compute the volume of each ETDRS sector to compute the vessel density
        center_mask, q1_mask, q2_mask, q3_mask, q4_mask = get_ETDRS_grid_masks(np.ones_like(faz), center_radius=args.center_radius/args.mm*faz.shape[0], inner_radius=args.inner_radius/args.mm*faz.shape[0])
        AREA_FACTOR_MAP = {
            "C0": center_mask.sum(),
            "S1": q1_mask.sum(),
            "N1": q2_mask.sum(),
            "I1": q3_mask.sum(),
            "T1": q4_mask.sum(),
        }
    else:
        AREA_FACTOR_MAP = {
            "full": np.ones_like(faz).sum()
        }
    SCALING_FACTOR = args.mm * 1000 / faz.shape[0]

    if args.radius_thresholds:
        THRESHOLDS = [int(t) for t in args.radius_thresholds.split(",")]
    else:
        THRESHOLDS = []
    THRESHOLDS = [None,*THRESHOLDS,None]

    d: list[dict] = list()
    for data_file in tqdm(data_files):
        df = pandas.read_csv(data_file, sep=';')
        df = df[sanity_filter(df)]

        if args.etdrs:
            group, image_ID, name = data_file.split("/")[-3:]
        else:
            group, name = data_file.split("/")[-2:]
            image_ID = remove_extentions(name)
        image_ID = image_ID.removeprefix("pred_")
        
        sector_codes = [k for k in AREA_FACTOR_MAP.keys() if k in name]
        assert len(sector_codes) == 1, f"The file name must contain the sector code! The following codes have been found: {sector_codes}. Name is {name}"
        area = sector_codes[0]
        area_factor = AREA_FACTOR_MAP[area]

        if area == "C0" or area=="full":
            dd = dict()
            dd["Image_ID"] = remove_eye_code(remove_plexus_code(image_ID))
            dd["Group"] = remove_eye_code(remove_plexus_code(group))
            dd["Eye"] = "OD" if "OD" in image_ID else "OS"
            dd["Layer"] = "SVC" if "svc" in data_file.lower() else "DVC"

            if faz_map:
                dd["FAZ area [mm2]"] = faz_map.get(code_name(data_file).removesuffix(f"_{area}") , nan)
            
            for a in AREA_FACTOR_MAP.keys():
                for i in range(len(THRESHOLDS)-1):
                    lower, upper = THRESHOLDS[i],THRESHOLDS[i+1]
                    title = f"{a} Density ("
                    if lower is not None:
                         title += f"{lower}um < "
                    title += "radius"
                    if upper is not None:
                        title += f" < {upper}um"
                    title += ") [%]"
                    dd[title] = nan
        else:
            dd = d[-1]

        for i in range(len(THRESHOLDS)-1):
            condition=np.array(df.shape[0]*[True])
            lower, upper = THRESHOLDS[i],THRESHOLDS[i+1]
            title = f"{area} Density ("
            if lower is not None:
                title += f"{lower}um < "
                if condition.size>0:
                    condition &= np.array(df.avgRadiusAvg) * SCALING_FACTOR / args.radius_correction_factor > lower
            title += "radius"
            if upper is not None:
                title += f" < {upper}um"
                if condition.size>0:
                    condition &= np.array(df.avgRadiusAvg) * SCALING_FACTOR / args.radius_correction_factor < upper
            title += ") [%]"
            if df[condition].shape[0]>0:
                if args.from_3d:
                    dd[title] = (2*df[condition].volume).divide(df[condition].avgRadiusAvg * pi).sum() / area_factor * 100 # Rescale 3D volume to 2D area
                else:
                    dd[title] = df[condition].volume.sum() / area_factor * 100
            else:
                dd[title] = 0
        if area=="C0" or area=="full":
            d.append(dd)

    df = pandas.DataFrame(d)
    df = df.sort_values(by="Image_ID",key=natsort_keygen())
    output_dir = args.output_dir or args.source_dir
    if args.etdrs:
        output_name = "density_measurements_etdrs.csv"
    else:
        output_name = "density_measurements_full.csv"
    df.to_csv(os.path.join(output_dir,output_name), index=False, sep=",")
