import glob
import os
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd
from natsort import natsort_keygen, natsorted
from numpy import nan
from PIL import Image
from tqdm import tqdm
from utils.ETDRS_grid import get_ETDRS_grid_masks
from utils.visualizer import generate_image_from_graph_json


def remove_plexus_code(name: str):
    """Remove plexus layer codes from filename."""
    for code in ["_DCP", "_dcp", "_DVC", "_dvc", "_SCP", "_scp", "_SVC", "_svc"]:
        name = name.replace(code, "")
    return name

def remove_eye_code(name: str):
    """Remove eye codes (OS/OD) from filename."""
    return name.replace("_OS", "").replace("_OD", "")


def remove_extensions(basename: str):
    """Remove file extensions and suffixes from basename."""
    return basename.replace(" .", ".").removesuffix(".png").removesuffix("_edges.csv").removesuffix("_full")


def code_name(path: str):
    """Extract standardized code name from file path."""
    return (remove_prefixes(remove_plexus_code(remove_extensions(os.path.basename(path))).removeprefix("faz_"))
            .replace(" OCTA", "")
            .replace(" ", "_")
            .replace("__", "_"))

def remove_prefixes(name: str):
    return name.removeprefix("model_").removeprefix("pred_")


def generate_density_title(area: str, lower: int, upper: int) -> str:
    """Generate density column title based on area and radius thresholds."""
    title = f"{area} Density ("
    if lower is not None:
        title += f"{lower}um < "
    title += "radius"
    if upper is not None:
        title += f" < {upper}um"
    title += ") [%]"
    return title


def process_file_pair(args_tuple):
    """Process a single file pair for parallel execution."""
    (data_file, graph_file, segmentation_files, faz_map, AREA_FACTOR_MAP, 
     THRESHOLDS, thresholds, args_etdrs, args_mm, args_radius_correction_factor, faz_shape) = args_tuple
    
    edge_df = pd.read_csv(data_file, sep=';', index_col=0)
    graph_json = pd.read_json(graph_file, orient='records')

    # Parse file path to extract metadata
    if args_etdrs:
        group, image_ID, name = data_file.split("/")[-3:]
    else:
        group, name = data_file.split("/")[-2:]
        image_ID = remove_extensions(name)
    image_ID = remove_prefixes(image_ID)
    
    # Determine area sector
    sector_codes = [k for k in AREA_FACTOR_MAP.keys() if k in name]
    assert len(sector_codes) == 1, f"The file name must contain the sector code! Found: {sector_codes}. Name: {name}. Make sure you use --etdrs for ETDRS analysis."
    area = sector_codes[0]
    area_factor = AREA_FACTOR_MAP[area]

    # Initialize data dictionary for primary areas
    if area in ("C0", ""):
        dd = {
            "Image_ID": remove_eye_code(remove_plexus_code(image_ID)),
            "Group": remove_eye_code(remove_plexus_code(group)),
            "Eye": "OD" if "OD" in image_ID else "OS",
            "Layer": "SVC" if "svc" in data_file.lower() else "DVC"
        }
        
        if faz_map:
            dd["FAZ area [mm2]"] = faz_map.get(code_name(data_file).removesuffix(f"_{area}"), nan)
        
        # Initialize all density columns with NaN
        for a in AREA_FACTOR_MAP.keys():
            for i in range(len(THRESHOLDS)-1):
                dd[generate_density_title(a, THRESHOLDS[i], THRESHOLDS[i+1])] = nan
        new_entry = True
    else:
        dd = {}
        new_entry = False

    # Compute densities for each radius interval
    radius_intervals = list(zip([0] + [t/1000 for t in thresholds], 
                                    [t/1000 for t in thresholds] + [np.inf]))
    
    # Find the corresponding segmentation file
    seg_file = next((f for f in segmentation_files if remove_prefixes(remove_extensions(os.path.basename(f))) == image_ID), None)
    if seg_file is None:
        raise FileNotFoundError(f"No segmentation file found for {data_file} with code {image_ID}!")
    seg_img = np.array(Image.open(seg_file), np.float32)/255

    graph_images = []
    for t in radius_intervals:
        graph_img_filtered_t = generate_image_from_graph_json(
            graph_json=graph_json, edges_df=edge_df, radius_interval=t,
            dim=faz_shape[0], image_size_mm=args_mm, colorize="white", radius_correction_factor=args_radius_correction_factor
        ).astype(np.float32)/255 * seg_img
        graph_images.append(graph_img_filtered_t)
    
    # Normalize overlapping pixels and calculate densities
    graph_img = np.stack(graph_images, axis=-1).sum(-1)
    densities = []
    for img in graph_images:
        mask = (graph_img > 0) & (img > 0)
        img[mask] /= graph_img[mask]
        densities.append(img.sum() / area_factor * 100)

    # Store densities in the data dictionary
    for i in range(len(THRESHOLDS)-1):
        title = generate_density_title(area, THRESHOLDS[i], THRESHOLDS[i+1])
        dd[title] = densities[i] if edge_df.shape[0] > 0 else 0
    
    return dd, new_entry, area

def generate_anylsis_file(
        source_dir: str,
        segmentation_dir: str,
        output_dir: str = None,
        faz_files: str = None,
        radius_thresholds: str = "0,inf",
        mm: float = 3.0,
        etdrs: bool = False,
        center_radius: float = 3/6,
        inner_radius: float = 3/2.4,
        radius_correction_factor: float = -1.0,
        threads: int = cpu_count() - 1,
        **kwargs
):
        # Find and validate input files
    edge_files = natsorted(glob.glob(os.path.join(source_dir, "**/*_edges.csv"), recursive=True))
    graph_files = natsorted(glob.glob(os.path.join(source_dir, "**/*_graph.json"), recursive=True))
    segmentation_files = natsorted(glob.glob(os.path.join(segmentation_dir, "**/*.png"), recursive=True))
    assert edge_files, f"No '_edges.csv' files found in folder {source_dir}!"
    assert graph_files, f"No '_graph.json' files found in folder {source_dir}!"

    # Process FAZ files if provided
    faz_map = {}
    if faz_files:
        faz_files = natsorted(glob.glob(faz_files, recursive=True))
        if not faz_files:
            print(f"No files found in faz folder {faz_files}!")
        
        for faz_file in tqdm(faz_files, desc="Processing FAZ files"):
            faz = np.array(Image.open(faz_file))
            image_area = faz.shape[0] * faz.shape[1]
            faz_area = (faz/255).sum() / image_area * mm**2
            faz_map[code_name(faz_file)] = faz_area

    # Setup area masks and factors
    if etdrs:
        assert faz_map, "FAZ files are required for ETDRS analysis!"
        center_mask, q1_mask, q2_mask, q3_mask, q4_mask = get_ETDRS_grid_masks(
            np.ones_like(faz), 
            center_radius=center_radius/mm*faz.shape[0], 
            inner_radius=inner_radius/mm*faz.shape[0]
        )
        AREA_FACTOR_MAP = {"C0": center_mask.sum(), "S1": q1_mask.sum(), "N1": q2_mask.sum(), "I1": q3_mask.sum(), "T1": q4_mask.sum()}
    else:
        AREA_FACTOR_MAP = {"": np.ones_like(faz).sum()}

    
    thresholds = [float(t) for t in radius_thresholds.split(",")] if radius_thresholds else []
    THRESHOLDS = [None, *thresholds, None]

    # Prepare arguments for parallel processing
    process_args = []
    for data_file, graph_file in zip(edge_files, graph_files):
        args_tuple = (
            data_file, graph_file, segmentation_files, faz_map, AREA_FACTOR_MAP,
            THRESHOLDS, thresholds, etdrs, mm, radius_correction_factor, faz.shape
        )
        process_args.append(args_tuple)

    # Process files in parallel
    d = []
    
    print(f"Using {threads} threads for processing graph features.")
    with Pool(threads) as pool:
        results = list(tqdm(pool.imap(process_file_pair, process_args), total=len(process_args), desc="Processing files"))
    
    # Reconstruct the data structure maintaining original order and logic
    current_entry = None
    for i, (dd, new_entry, area) in enumerate(results):
        if new_entry:  # Primary area (C0 or "")
            if current_entry is not None:
                d.append(current_entry)
            current_entry = dd.copy()
        else:  # Secondary area - merge with current entry
            if current_entry is not None:
                current_entry.update(dd)
    
    # Add the last entry
    if current_entry is not None:
        d.append(current_entry)

    # Save results
    df = pd.DataFrame(d)
    df = df.sort_values(by="Image_ID", key=natsort_keygen())
    output_dir = output_dir or source_dir
    output_name = "density_measurements_etdrs.csv" if etdrs else "density_measurements_full.csv"
    df.to_csv(os.path.join(output_dir, output_name), index=False, sep=",")
    print(f"Analysis summary saved to {os.path.join(output_dir, output_name)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate analysis summary from OCTA graph data.')
    parser.add_argument('--source_dir', type=str, help="Absolute path to the folder graph features", required=True)
    parser.add_argument('--segmentation_dir', type=str, help="Absolute path to the segmentation maps", required=True)

    parser.add_argument('--output_dir', type=str, help="Absolute path to the output folder. If none is given, save in source folder.")
    parser.add_argument('--faz_files', type=str, help="Absolute path to the faz segmentation files. Required for etdrs analysis.")
    
    parser.add_argument('--radius_thresholds', type=str, default="0,inf", help="Comma separated list of thresholds for vessel stratification [um].")
    parser.add_argument('--mm', type=float, default=3.0, help="Height of the segmentation volume in mm. Default is 3 mm")
    parser.add_argument('--etdrs', action="store_true", help="If set, use ETDRS grid stratification")
    parser.add_argument('--radius_correction_factor', type=float, default=-1.0, 
                        help="Additive correction factor for the radius estimation. Default is -1.0 to correct for Voreen's overestimation by 1 pixel measured on synthetic data.")
    parser.add_argument('--center_radius', type=float, default=3/6, help="Radius of ETDRS center radius in mm")
    parser.add_argument('--inner_radius', type=float, default=3/2.4, help="Radius of ETDRS center radius in mm")
    parser.add_argument('--threads', type=int, default=max(1, cpu_count()-1), help="Number of threads to use for parallel processing. Default is all available cores minus one.")
    args = parser.parse_args()
    kwargs = vars(args)

    generate_anylsis_file(**kwargs)
