import argparse
import concurrent.futures
import glob
import os
import pathlib
from multiprocessing import cpu_count

import docker
import nibabel as nib
import numpy as np
from dotenv import load_dotenv
from natsort import natsorted
from PIL import Image
from scipy import ndimage
from tqdm import tqdm
from utils.convert_2d_to_3d import convert_2d_to_3d
from utils.ETDRS_grid import get_ETDRS_grid_indices
from utils.voreen_vesselgraphextraction import extract_vessel_graph

load_dotenv()
project_folder = str(pathlib.Path(__file__).parent.resolve())

DOCKER_VOREEN_BIN = "/home/software/voreen-voreen-5.3.0/voreen/bin/"
DOCKER_WORK_DIR = '/var/results'

if __name__ == "__main__":
    # Parse input arguments
    parser = argparse.ArgumentParser(
        description='Extract vessel graphs from OCTA images using Voreen.\
            \nPlease note that the predicted radii by Voreen might be subject to small additive error factor.\
            You can manually configure the necessary correction factor for image plotting with the --radius_correction_factor argument.\
            On synthetic data, we measured 1 pixel overestimation, hence this is the default.')
    parser.add_argument('--image_files', help="Absolute path to the segmentation maps", type=str, required=True)
    parser.add_argument('--tmp_dir', help="Absolute path to the temporary directory where voreen will store its temporary files", type=str, default=os.getenv("DOCKER_TMP_DIR", "/var/tmp"))

    parser.add_argument('--output_dir', help="Absolute path to the folder where the graph and feature files should be stored."
                        +"If no folder is provided, the files will be stored in the same directory as the source images.", type=str, default=None)
    parser.add_argument('--voreen_image_name', help="Absolute path to the bin folder of your voreen installation", type=str, default="voreen")
    
    parser.add_argument('--voreen_workspace', help="Absolute path to the voreen workspace file", type=str, default=project_folder+"/voreen/feature-vesselgraphextraction_customized_command_line.vws")
    parser.add_argument('--bulge_size', help="Numeric value of the bulge_size parameter to control the sensitivity", type=float, default=3)
    parser.add_argument('--graph_image', help="Generate an image of the extracted graph", action="store_true", default=True)
    parser.add_argument('--no_graph_image', help="Do not generate an image of the extracted graph", action="store_false", dest="colorize_graph")
    parser.add_argument('--colorize', help="Generate colored radius graph", choices=["continuous", "thresholds", "random", "white"], default="continuous")
    parser.add_argument('--thresholds', help="Radius thresholds for colorization", type=str, default=None)
    parser.add_argument('--generate_graph_file', help="Generate the graph JSON file", action="store_true", default=True)
    parser.add_argument('--no_generate_graph_file', help="Do not generate the graph JSON file", action="store_false", dest="generate_graph_file")
    parser.add_argument('--verbose', action="store_true", help="Print log information from voreen")
    parser.add_argument('--z_dim', help="Z dimension of the 3D segmentation mask. Only needed for 2D segmentation masks.", type=int, default=64)

    parser.add_argument('--etdrs', action="store_true", help="Analyse vessels in ETDRS grid")
    parser.add_argument('--mm', help="Size of the image in mm. Default is 3 mm", type=float, default=3.0)
    parser.add_argument('--radius_correction_factor', help="Additive correction factor for the radius estimation. Default is -1.0 to correct for Voreen's overestimation by 1 pixel measured on synthetic data.", type=float, default=-1.0)
    parser.add_argument('--faz_dir', help="Absolute path to the folder containing all the faz segmentation maps. Only needed for ETDRS analysis", type=str, default=None)
    parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=-1)

    args = parser.parse_args()
    # Clean tmpdir
    if os.path.exists(args.tmp_dir):
        os.system(f"rm -rf '{os.path.join(args.tmp_dir, "*")}'")

    ves_seg_files = [p for p in natsorted(glob.glob(args.image_files, recursive=True))]
    assert len(ves_seg_files)>0, f"Found no matching vessel segmentation files for path {args.image_files}!"
    source_dir = os.path.dirname(os.path.commonprefix(ves_seg_files))

    color_thresholds = [float(t) for t in args.thresholds.split(",")] if args.thresholds is not None else None

    container_name = None
    # Check if we're running in Docker (DooD setup)
    running_in_docker = os.path.exists("/.dockerenv")
    
    # Check if a voreen container from docker-compose is already running
    docker_compose_container = None
    client = docker.from_env()
    for container in client.containers.list(filters={"status": "running"}):
        if container.name == "voreen-container":  # docker-compose container name
            docker_compose_container = container
            container_name = container.name
            print(f"Found existing docker-compose Voreen container: {container_name}")
            break
    
    # Start docker container if not running in docker and no docker-compose container found
    if not running_in_docker and docker_compose_container is None:
        # Check if container of this image is running
        client = docker.from_env()
        for container in client.containers.list(filters={"status": "running"}):
            if container.image.tags and any(args.voreen_image_name in tag for tag in container.image.tags):
                container_name = container.name
                break
        if container_name is None:
            print(f"No running container for image {args.voreen_image_name} found. Starting a new container...")
            container = client.containers.run(
                image=args.voreen_image_name,
                detach=True,
                tty=True,
                stdin_open=True,
                command="tail -f /dev/null",
                user=f"{os.getuid()}:{os.getgid()}",
                volumes={
                    args.tmp_dir: {'bind': "/var/tmp", 'mode': 'rw'},
                    source_dir: {'bind': "/var/src", 'mode': 'ro'},
                    args.output_dir: {'bind': "/var/results", 'mode': 'rw'}
                },
            )
            container_name = container.name
            # Ensure Voreen can write to its internal data directory
            container.exec_run(user="root", cmd=f"chmod 777 -R {DOCKER_VOREEN_BIN}/../data")
    elif running_in_docker:
        print("Running in Docker container. Using DooD setup to communicate with Voreen container.")
        # In DooD setup, we need to start the Voreen container from within our Python container
        client = docker.from_env()
        for container in client.containers.list(filters={"status": "running"}):
            if container.image.tags and any(args.voreen_image_name in tag for tag in container.image.tags):
                container_name = container.name
                break
        if container_name is None:
            print(f"No running container for image {args.voreen_image_name} found. Starting a new container...")
            container = client.containers.run(
                image=args.voreen_image_name,
                detach=True,
                tty=True,
                stdin_open=True,
                command="tail -f /dev/null",
                user=f"{os.getuid()}:{os.getgid()}",
                volumes={
                    args.tmp_dir: {'bind': "/var/tmp", 'mode': 'rw'},
                    source_dir: {'bind': "/var/src", 'mode': 'ro'},
                    args.output_dir: {'bind': "/var/results", 'mode': 'rw'}
                },
            )
            container_name = container.name
            # Ensure Voreen can write to its internal data directory
            container.exec_run(user="root", cmd=f"chmod 777 -R {DOCKER_VOREEN_BIN}/../data")

    if args.etdrs:
        assert bool(args.faz_dir)

        def get_code_name(path: str) -> str:
            extension = ".nii.gz" if path.endswith(".nii.gz") else "."+path.split(".")[-1]
            return os.path.basename(path).removesuffix(extension).removeprefix("faz_").removeprefix("model_").removeprefix("model_")

        faz_seg_files = natsorted(glob.glob(f'{args.faz_dir}/**/*.*', recursive=True))
        assert len(faz_seg_files)>0, f"Found no matching FAZ files at path {args.faz_dir}! Note, this script currently only supports .png, .jpg, and .bmp faz segmentation files."

        faz_code_name_map = {get_code_name(path): path for path in faz_seg_files if ("dvc" in path.lower()) or ("dcp" in path.lower())}


        def task(ves_seg_path: str):
            extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
            image_name = os.path.basename(ves_seg_path).removesuffix(extension)
            if args.output_dir is None:
                output_dir = os.path.dirname(ves_seg_path)
            else:
                output_dir = args.output_dir
            output_dir= os.path.join(os.path.dirname(ves_seg_path).replace(source_dir, output_dir),image_name.removesuffix(extension))
            os.makedirs(output_dir, exist_ok=True)
            
            if extension == ".nii.gz":
                img_nii: nib.Nifti1Image = nib.load(ves_seg_path)
                ves_seg_3d = img_nii.get_fdata(dtype=np.uint8)
            else:
                ves_seg = np.array(Image.open(ves_seg_path), np.uint8)
                ves_seg_3d = convert_2d_to_3d(ves_seg, z_dim=args.z_dim)
            
            faz_code_name = get_code_name(ves_seg_path).replace("SVC", "DVC").replace("svc", "dvc")
            if faz_code_name not in faz_code_name_map:
                print(f"Skipping analysis for image {ves_seg_path}. No FAZ found.")
                return

            faz_seg = np.array(Image.open(faz_code_name_map[faz_code_name]))
            center = ndimage.center_of_mass(faz_seg)
            ETDRS_grid_indices = get_ETDRS_grid_indices(center)
            if "OS" in faz_code_name:
                suffixes = ["C0", "S1", "N1", "I1", "T1"]
            else:
                suffixes = ["C0", "S1", "T1", "I1", "N1"]


            for indices, suffix in zip(ETDRS_grid_indices, suffixes):
                mask = np.zeros_like(faz_seg, dtype=np.bool_)
                try:
                    mask[indices] = True
                except IndexError:
                    continue

                ves_seg_masked = np.copy(ves_seg_3d)
                ves_seg_masked[~mask,:] = 0

                header = nib.Nifti1Header()
                header.set_xyzt_units(xyz="mm", t="sec")
                header.set_data_shape(ves_seg_3d.shape)
                ves_seg_masked_nii = nib.Nifti1Image(ves_seg_masked, np.eye(4), header=header)
                
                # Compute graph
                extract_vessel_graph(
                    img_nii=ves_seg_masked_nii,
                    image_name=f"{image_name}_{suffix}",
                    outdir=f"{output_dir}",
                    DOCKER_WORK_DIR=f"{DOCKER_WORK_DIR}/{image_name}",
                    tmp_dir=args.tmp_dir,
                    bulge_size=args.bulge_size,
                    workspace_file=args.voreen_workspace,
                    container_name=container_name,
                    graph_image=args.graph_image,
                    colorize=args.colorize,
                    color_thresholds=color_thresholds,
                    verbose=bool(args.verbose),
                    image_size_mm=args.mm
                )
    else:
        def task(ves_seg_path: str):
            extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
            image_name = os.path.basename(ves_seg_path).removesuffix(extension)
            if args.output_dir is None:
                output_dir = os.path.dirname(ves_seg_path)
            else:
                output_dir = args.output_dir
            output_dir = os.path.dirname(ves_seg_path).replace(source_dir, output_dir)
            os.makedirs(output_dir, exist_ok=True)
            
            if extension == ".nii.gz":
                img_nii = nib.load(ves_seg_path)
            else:
                ves_seg = np.array(Image.open(ves_seg_path), np.uint8)
                ves_seg_3d = convert_2d_to_3d(ves_seg, z_dim=args.z_dim)
                header = nib.Nifti1Header()
                header.set_xyzt_units(xyz="mm", t="sec")
                header.set_data_shape(ves_seg_3d.shape)
                img_nii = nib.Nifti1Image(ves_seg_3d, np.eye(4), header=header)

            extract_vessel_graph(
                img_nii=img_nii,
                image_name=image_name,
                outdir=output_dir,
                DOCKER_WORK_DIR=DOCKER_WORK_DIR,
                tmp_dir=args.tmp_dir,
                bulge_size=args.bulge_size,
                workspace_file=args.voreen_workspace,
                container_name=container_name,
                graph_image=args.graph_image,
                colorize=args.colorize,
                color_thresholds=color_thresholds,
                verbose=bool(args.verbose),
                radius_correction_factor=args.radius_correction_factor,
                image_size_mm=args.mm
            )

    if args.threads == -1:
        # If no argument is provided, use all available threads but one
        cpus = cpu_count()
        threads = min(cpus-1,len(ves_seg_files)) if cpus>1 else 1
    else:
        threads=args.threads

    try:
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
    except Exception as e:
        print(f"An error occurred during graph feature extraction:\n{e}")
    finally:
        if container_name is not None:
            client = docker.from_env()
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
            print(f"Container '{container_name}' stopped and removed.")
            if os.path.exists(args.tmp_dir):
                result = os.system(f"rm -rf {os.path.join(args.tmp_dir, '*')}")
                if result == 0:
                    print(f"Temporary directory {args.tmp_dir} cleaned up successfully.")
                else:
                    print(f"Failed to clean up temporary directory {args.tmp_dir}.")
