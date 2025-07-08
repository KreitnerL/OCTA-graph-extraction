import argparse
import os
import nibabel as nib
from PIL import Image
import numpy as np
from utils.voreen_vesselgraphextraction import extract_vessel_graph
from utils.visualizer import node_edges_to_graph
from utils.ETDRS_grid import get_ETDRS_grid_indices
import pathlib
from tqdm import tqdm
import glob
from natsort import natsorted
from scipy import ndimage
import uuid
from multiprocessing import cpu_count
import concurrent.futures
import pandas as pd

project_folder = str(pathlib.Path(__file__).parent.resolve())

# You may want to customize these
####################################################################################################
workspace_file = project_folder+"/voreen/feature-vesselgraphextraction_customized_command_line.vws"

# Any empty or non-existing folder with write access
workdir = project_folder+"/voreen/workdir/"
TMP_DIR = project_folder+"/voreen/tmpdir"
cachedir = project_folder+"/voreen/cachedir/"
####################################################################################################

def _sanity_filter(df_rows: pd.DataFrame, df_nodes: pd.DataFrame, z_dim, lower_z=0.3, upper_z=0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_nodes_filtered = df_nodes[(df_nodes.pos_z / z_dim > lower_z) & (df_nodes.pos_z / z_dim < upper_z)]
    df_rows_filtered = df_rows[
        (df_rows.volume>0) & (df_rows.distance>0) & (df_rows.curveness>0) & (df_rows.avgRadiusAvg>0) & (df_rows.avgRadiusStd)
    ]
    df_rows_filtered = df_rows_filtered.merge(df_nodes_filtered, left_on="node1id", right_on="id", how="inner")
    df_rows_filtered = df_rows_filtered.merge(df_nodes_filtered, left_on="node2id", right_on="id", how="inner")
    return df_rows_filtered, df_nodes_filtered

def extract_graph_features(img_nii: nib.Nifti1Image,
                           image_name: str,
                           output_dir: str,
                           voreen_tool_path: str,
                           bulge_size=5,
                           graph_image=True,
                           generate_graph_file=False,
                           colorize=False,
                           verbose=False,
                           ves_seg_3d=True,
                           thresholds: list[float]=None):
    while True:
        tempdir = f"{TMP_DIR}/{str(uuid.uuid4())}/"
        if not os.path.isdir(tempdir):
            break
    os.makedirs(tempdir)
    nii_path = os.path.join(tempdir, f'{image_name}.nii')
    nib.save(img_nii, nii_path)

    _ = extract_vessel_graph(nii_path, 
        output_dir+"/",
        tempdir,
        cachedir,
        bulge_size,
        workspace_file,
        voreen_tool_path,
        name=image_name,
        generate_graph_file=generate_graph_file,
        verbose=verbose
    )
    edges_file = os.path.join(output_dir, f'{image_name}_edges.csv')
    nodes_file = os.path.join(output_dir, f'{image_name}_nodes.csv')

    # Clean with sanity checks
    df_edges = pd.read_csv(edges_file, sep=";", index_col=0)
    df_nodes = pd.read_csv(nodes_file, sep=";", index_col=0)
    df_edges, df_nodes = _sanity_filter(df_edges,df_nodes, z_dim=img_nii.shape[2])
    df_nodes.to_csv(nodes_file, sep=";")
    df_edges.to_csv(edges_file, sep=";")
    # flush the files to disk
    os.sync()

    if graph_image:
        graph_img = node_edges_to_graph(nodes_file, edges_file, img_nii.shape[:2], colorize=colorize, radius_scale_factor=1 if ves_seg_3d else 2, thresholds=thresholds)
        Image.fromarray(graph_img.astype(np.uint8)).save(os.path.join(output_dir, f'{image_name}_graph.png'))

if __name__ == "__main__":
    # Parse input arguments
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--image_files', help="Absolute path to the segmentation maps", type=str, required=True)
    parser.add_argument('--voreen_tool_path', help="Absolute path to the bin folder of your voreen installation", type=str, required=True)
    parser.add_argument('--output_dir', help="Absolute path to the folder where the graph and feature files should be stored."
                        +"If no folder is provided, the files will be stored in the same directory as the source images.", type=str, default=None)
    parser.add_argument('--bulge_size', help="Numeric value of the bulge_size parameter to control the sensitivity", type=float, default=3)
    parser.add_argument('--graph_image', help="Generate an image of the extracted graph", action="store_true", default=True)
    parser.add_argument('--no_graph_image', help="Do not generate an image of the extracted graph", action="store_false", dest="colorize_graph")
    parser.add_argument('--colorize_graph', help="Generate colored radius graph", action="store_true", default=True)
    parser.add_argument('--no_colorize_graph', help="Generate colored radius graph", action="store_false", dest="colorize_graph")
    parser.add_argument('--thresholds', help="Radius thresholds for colorization", type=str, default=None)
    parser.add_argument('--generate_graph_file', help="Generate the graph JSON file", action="store_true", default=False)
    parser.add_argument('--verbose', action="store_true", help="Print log information from voreen")

    parser.add_argument('--ETDRS', action="store_true", help="Analyse vessels in ETDRS grid")
    parser.add_argument('--faz_dir', help="Absolute path to the folder containing all the faz segmentation maps. Only needed for ETDRS analysis", type=str, default=None)
    parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=-1)

    args = parser.parse_args()
    # Clean tmpdir
    if os.path.exists(TMP_DIR):
        os.system(f"rm -rf '{TMP_DIR}'")

    ves_seg_files = [p for p in natsorted(glob.glob(args.image_files, recursive=True))]
    assert len(ves_seg_files)>0, f"Found no matching vessel segmentation files for path {args.image_files}!"
    if any([p.split(".")[-1] in ["png", "jpg", "bmp"] for p in ves_seg_files]):
        print("Warning: Using voreen on 2D segmentation masks leads to an underestimation of the vessel radii. Consider using our 3D reconstruction tool for better performance.")
    source_dir = os.path.dirname(os.path.commonprefix(ves_seg_files))

    THRESHOLDS = [float(t) for t in args.thresholds.split(",")] if args.thresholds is not None else None

    if args.ETDRS:
        assert bool(args.faz_dir)

        def get_code_name(path: str) -> str:
            extension = ".nii.gz" if path.endswith(".nii.gz") else "."+path.split(".")[-1]
            return os.path.basename(path).removesuffix(extension).removeprefix("faz_").removeprefix("model_").removeprefix("model_")

        faz_seg_files = natsorted(glob.glob(f'{args.faz_dir}/**/*.*', recursive=True))
        assert len(faz_seg_files)>0, f"Found no matching FAZ files at path {args.faz_dir}! Note, this script currently only supports .png, .jpg, and .bmp faz segmentation files."

        faz_code_name_map = {get_code_name(path): path for path in faz_seg_files if ("dvc" in path.lower()) or ("dcp" in path.lower())}


        def task(ves_seg_path: str):
            image_name = os.path.basename(ves_seg_path)
            extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
            faz_code_name = get_code_name(ves_seg_path).replace("SVC", "DVC").replace("svc", "dvc")
            if faz_code_name not in faz_code_name_map:
                print(f"Skipping analysis for image {ves_seg_path}. No FAZ found.")
                return
            if extension == ".nii.gz":
                img_nii: nib.Nifti1Image = nib.load(ves_seg_path)
                ves_seg_3d = img_nii.get_fdata()
            else:
                ves_seg = np.array(Image.open(ves_seg_path))
                ves_seg_3d = np.stack([np.zeros_like(ves_seg), ves_seg, np.zeros_like(ves_seg)], axis=-1)

            faz_seg = np.array(Image.open(faz_code_name_map[faz_code_name]))
            center = ndimage.center_of_mass(faz_seg)
            ETDRS_grid_indices = get_ETDRS_grid_indices(center)
            if "OS" in faz_code_name:
                suffixes = ["C0", "S1", "N1", "I1", "T1"]
            else:
                suffixes = ["C0", "S1", "T1", "I1", "N1"]

            if args.output_dir is None:
                output_dir = os.path.dirname(ves_seg_path)
            else:
                output_dir = args.output_dir
            output_dir= os.path.join(os.path.dirname(ves_seg_path).replace(source_dir, output_dir),image_name.removesuffix(extension))
            os.makedirs(output_dir, exist_ok=True)

            for indices, suffix in zip(ETDRS_grid_indices, suffixes):
                mask = np.zeros_like(faz_seg, dtype=np.bool_)
                try:
                    mask[indices] = True
                except IndexError:
                    continue

                ves_seg_masked = np.copy(ves_seg_3d)
                ves_seg_masked[~mask,:] = 0
                
                ves_seg_masked_nii = nib.Nifti1Image(ves_seg_masked.astype(np.uint8), np.eye(4))

                # Compute graph
                extract_graph_features(ves_seg_masked_nii,
                                       image_name.replace(extension, "_"+suffix),
                                       output_dir,
                                       args.voreen_tool_path,
                                       args.bulge_size,
                                       args.graph_image,
                                       args.generate_graph_file,
                                       args.colorize_graph,
                                       verbose=bool(args.verbose),
                                       ves_seg_3d=extension==".nii.gz",
                                       thresholds=THRESHOLDS)
    else:
        def task(ves_seg_path: str):
            extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
            if args.output_dir is None:
                output_dir = os.path.dirname(ves_seg_path)
            else:
                output_dir = args.output_dir
            output_dir = os.path.dirname(ves_seg_path).replace(source_dir, output_dir)
            os.makedirs(output_dir, exist_ok=True)
            if extension == ".nii.gz":
                img_nii = nib.load(ves_seg_path)
            else:
                a = np.array(Image.open(ves_seg_path))
                a = np.stack([np.zeros_like(a), a, np.zeros_like(a)], axis=-1)
                img_nii = nib.Nifti1Image(a.astype(np.uint8), np.eye(4))
            image_name = os.path.basename(ves_seg_path).removesuffix(extension)
            extract_graph_features(img_nii,
                                   image_name + "_full",
                                   output_dir,
                                   args.voreen_tool_path,
                                   args.bulge_size,
                                   args.graph_image,
                                   args.generate_graph_file,
                                   args.colorize_graph,
                                   verbose=bool(args.verbose),
                                   ves_seg_3d=extension==".nii.gz",
                                   thresholds=THRESHOLDS)

    if args.threads == -1:
        # If no argument is provided, use all available threads but one
        cpus = cpu_count()
        threads = min(cpus-1,len(ves_seg_files)) if cpus>1 else 1
    else:
        threads=args.threads

    if threads>1:
        # Multi processing
        with tqdm(total=len(ves_seg_files), desc="Extracting graph features...") as pbar:
            with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
                future_dict = {executor.submit(task, ves_seg_files[i]): i for i in range(len(ves_seg_files))}
                for future in concurrent.futures.as_completed(future_dict):
                    i = future_dict[future]
                    pbar.update(1)
    else:
        # Single processing
        for ves_seg_path in tqdm(ves_seg_files, desc="Extracting graph features..."):
            task(ves_seg_path)
