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

project_folder = str(pathlib.Path(__file__).parent.resolve())

# You may want to customize these
####################################################################################################
workspace_file = project_folder+"/voreen/feature-vesselgraphextraction_customized_command_line.vws"

# Any empty or non-existing folder with write access
workdir = project_folder+"/voreen/workdir/"
TMP_DIR = project_folder+"/voreen/tmpdir"
cachedir = project_folder+"/voreen/cachedir/"
####################################################################################################

def extract_graph_features(img_nii: nib.Nifti1Image,
                           image_name: str,
                           output_dir: str,
                           bulge_size=5,
                           voreen_tool_path="/home/linus/Software/voreen-src-unix-nightly/bin",
                           graph_image=True,
                           generate_graph_file=False,
                           colorize=False,
                           verbose=False,
                           ves_seg_3d=True):
    tempdir = f"{TMP_DIR}/{str(uuid.uuid4())}/"
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
    nodes_file = os.path.join(output_dir, f'{image_name}_nodes.csv')
    edges_file = os.path.join(output_dir, f'{image_name}_edges.csv')
    if graph_image:
        graph_img = node_edges_to_graph(nodes_file, edges_file, img_nii.shape[:2], colorize=colorize, radius_scale_factor=1 if ves_seg_3d else 2)
        Image.fromarray(graph_img.astype(np.uint8)).save(os.path.join(output_dir, f'{image_name}_graph.png'))

if __name__ == "__main__":
    # Parse input arguments
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--image_dir', help="Absolute path to the folder containing all the segmentation maps", type=str, required=True)
    parser.add_argument('--voreen_tool_path', help="Absolute path to the bin folder of your voreen installation", type=str, required=True)
    parser.add_argument('--output_dir', help="Absolute path to the folder where the graph and feature files should be stored."
                        +"If no folder is provided, the files will be stored in the same directory as the source images.", type=str, default=None)
    parser.add_argument('--bulge_size', help="Numeric value of the bulge_size parameter to control the sensitivity", type=float, default=3)
    parser.add_argument('--graph_image', help="Generate an image of the extracted graph", type=bool, default=True)
    parser.add_argument('--colorize_graph', help="Generate colored radius graph", type=bool, default=True)
    parser.add_argument('--generate_graph_file', help="Generate the graph JSON file", type=bool, default=False)
    parser.add_argument('--verbose', action="store_true", help="Print log information from voreen")

    parser.add_argument('--ETDRS', action="store_true", help="Analyse vessels in ETDRS grid")
    parser.add_argument('--faz_dir', help="Absolute path to the folder containing all the faz segmentation maps. Only needed for ETDRS analysis", type=str, default=None)
    parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=-1)

    args = parser.parse_args()
    # Clean tmpdir
    if os.path.exists(TMP_DIR):
        os.system(f"rm -rf '{TMP_DIR}'")

    ves_seg_files = [p for p in natsorted(glob.glob(f'{args.image_dir}/**/*', recursive=True)) if os.path.isfile(p) and p.endswith((".png", ".jpg",".bmp",".nii.gz"))]
    assert len(ves_seg_files)>0, f"Found no matching vessel segmentation files at path {args.image_dir}! Note, this script currently only supports .png, .jpg, .bmp, and .nii.gz vessel segmentation files."
    if any([p.split(".")[-1] in ["png", "jpg", "bmp"] for p in ves_seg_files]):
        print("Warning: Using voreen on 2D segmentation masks leads to an underestimation of the vessel radii. Consider using our 3D reconstruction tool for better performance.")
    if args.ETDRS:
        assert bool(args.faz_dir)

        def get_code_name(filename: str) -> str:
            return filename.removeprefix("faz_").removeprefix("model_").removeprefix("pred_").replace(" - Kopie", "").replace(" ", "_").removesuffix(".png").removesuffix("_OCTA").replace("DCP", "DVC")

        faz_seg_files = natsorted(glob.glob(f'{args.faz_dir}/**/*', recursive=True))
        assert len(faz_seg_files)>0, f"Found no matching FAZ files at path {args.faz_dir}! Note, this script currently only supports .png, .jpg, and .bmp faz segmentation files."

        dvc_faz_code_name_map = {get_code_name(path.split("/")[-1]): path for path in faz_seg_files if ("DVC" in path) or ("DCP" in path)}

        def task(ves_seg_path: str):
            name = ves_seg_path.split("/")[-1]
            extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
            if extension == ".nii.gz":
                image_name = '.'.join(name.split(".")[:-2])
                faz_code_name = get_code_name(image_name).replace("SVC", "DVC").replace(extension, ".png")
                if faz_code_name not in dvc_faz_code_name_map:
                    return
                img_nii: nib.Nifti1Image = nib.load(ves_seg_path)
                ves_seg_3d = img_nii.get_fdata()
            else:
                faz_code_name = get_code_name(ves_seg_path.split("/")[-1]).replace("SVC", "DVC")
                if faz_code_name not in dvc_faz_code_name_map:
                    return
                ves_seg = np.array(Image.open(ves_seg_path))
                ves_seg_3d = np.stack([np.zeros_like(ves_seg), ves_seg, np.zeros_like(ves_seg)], axis=-1)

            faz_seg = np.array(Image.open(dvc_faz_code_name_map[faz_code_name]))
            center = ndimage.center_of_mass(faz_seg)
            ETDRS_grid_indices = get_ETDRS_grid_indices(center)
            if "OS" in faz_code_name:
                suffixes = ["C0", "S1", "N1", "I1", "T1"]
            else:
                suffixes = ["C0", "S1", "T1", "I1", "N1"]

            output_dir = ves_seg_path.removesuffix(extension)
            if args.output_dir is not None:
                output_dir = output_dir.replace(args.image_dir, args.output_dir)
                if not os.path.isdir(output_dir):
                    os.makedirs(output_dir)

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
                extract_graph_features(ves_seg_masked_nii, name.replace(extension, "_"+suffix), output_dir, args.bulge_size, args.voreen_tool_path, args.graph_image, args.generate_graph_file, args.colorize_graph, verbose=bool(args.verbose), ves_seg_3d=extension==".nii.gz")
    else:
        def task(ves_seg_path: str):
            output_dir = '/'.join(ves_seg_path.split('/')[:-1])
            extension = ".nii.gz" if ves_seg_path.endswith("-nii.gz") else "."+ves_seg_path.split(".")[-1]
            if args.output_dir is not None:
                output_dir = output_dir.replace(args.image_dir, args.output_dir)
                if not os.path.isdir(output_dir):
                    os.makedirs(output_dir)
            if extension == ".nii.gz":
                image_name = '.'.join(ves_seg_path.split("/")[-1].split(".")[:-2])
                img_nii = nib.load(ves_seg_path)
            else:
                image_name = '.'.join(ves_seg_path.split("/")[-1].split(".")[:-1])
                a = np.array(Image.open(ves_seg_path))
                a = np.stack([np.zeros_like(a), a, np.zeros_like(a)], axis=-1)
                img_nii = nib.Nifti1Image(a.astype(np.uint8), np.eye(4))
            extract_graph_features(img_nii, image_name, output_dir, args.bulge_size, args.voreen_tool_path, args.graph_image, args.generate_graph_file, args.colorize_graph, verbose=bool(args.verbose), ves_seg_3d=extension==".nii.gz")

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
