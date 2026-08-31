import argparse
import concurrent.futures
import glob
import os
import pathlib
import tempfile
from functools import partial
from multiprocessing import cpu_count

import nibabel as nib
import numpy as np
from dotenv import load_dotenv
from natsort import natsorted
from PIL import Image
from scipy import ndimage
from tqdm import tqdm

import docker
from utils.convert_2d_to_3d import convert_2d_to_3d
from utils.ETDRS_grid import get_ETDRS_grid_indices
from utils.voreen_vesselgraphextraction import extract_vessel_graph

load_dotenv()
project_folder = str(pathlib.Path(__file__).parent.resolve())

DOCKER_VOREEN_BIN = "/home/software/voreen-voreen-5.3.0/voreen/bin/"
DOCKER_WORK_DIR = '/var/results'


def docker_work_dir_for_output(outdir: str, output_mount_dir: str) -> str:
    """Return the Voreen-container output path corresponding to a host/container output dir."""
    rel_outdir = os.path.relpath(os.path.abspath(outdir), os.path.abspath(output_mount_dir))
    if rel_outdir == ".":
        return DOCKER_WORK_DIR
    return os.path.join(DOCKER_WORK_DIR, rel_outdir)


def ensure_writable_output_dir(path: str) -> None:
    """Create an output directory before Docker can create it as root-owned."""
    os.makedirs(path, exist_ok=True)
    try:
        with tempfile.TemporaryFile(dir=path):
            pass
    except PermissionError as _:
        try:
            os.rmdir(path)
            os.makedirs(path, exist_ok=True)
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError as repair_exc:
            raise PermissionError(
                f"Output directory is not writable: {path}\n"
                "If Docker created it as root, fix it with:\n"
                f"  sudo chown -R $USER:$USER '{path}'\n"
                "or remove it if it is empty and rerun the pipeline."
            ) from repair_exc
        except PermissionError as repair_exc:
            raise PermissionError(
                f"Output directory is not writable: {path}\n"
                "If Docker created it as root, fix it with:\n"
                f"  sudo chown -R $USER:$USER '{path}'"
            ) from repair_exc

def get_code_name(path: str) -> str:
    extension = ".nii.gz" if path.endswith(".nii.gz") else "."+path.split(".")[-1]
    return os.path.basename(path).removesuffix(extension).removeprefix("faz_").removeprefix("model_").removeprefix("model_")

def full_graph(
        ves_seg_path: str,
        source_dir: str,
        tmp_dir: str,
        output_dir: str,
        output_mount_dir: str,
        container_name: str,
        color_thresholds: list[float] = None,
        z_dim: int = 64,
        bulge_size: float = 3.0,
        voreen_workspace: str = project_folder + "/voreen/feature-vesselgraphextraction_customized_command_line.vws",
        graph_image: bool = True,
        colorize: str = "continuous",
        verbose: bool = False,
        mm: float = 3.0,
        radius_correction_factor: float = -1.0,
        **kwargs):
    extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
    image_name = os.path.basename(ves_seg_path).removesuffix(extension)
    if output_dir is None:
        output_dir = os.path.dirname(ves_seg_path)
    else:
        output_dir = output_dir
    outdir = os.path.dirname(ves_seg_path).replace(source_dir, output_dir)
    os.makedirs(outdir, exist_ok=True)
    docker_work_dir = docker_work_dir_for_output(outdir, output_mount_dir)
    
    if extension == ".nii.gz":
        img_nii = nib.load(ves_seg_path)
    else:
        ves_seg = np.array(Image.open(ves_seg_path), np.uint8)
        ves_seg_3d = convert_2d_to_3d(ves_seg, z_dim=z_dim)
        header = nib.Nifti1Header()
        header.set_xyzt_units(xyz="mm", t="sec")
        header.set_data_shape(ves_seg_3d.shape)
        img_nii = nib.Nifti1Image(ves_seg_3d, np.eye(4), header=header)

    extract_vessel_graph(
        img_nii=img_nii,
        image_name=image_name,
        outdir=outdir,
        DOCKER_WORK_DIR=docker_work_dir,
        tmp_dir=tmp_dir,
        bulge_size=bulge_size,
        workspace_file=voreen_workspace,
        container_name=container_name,
        graph_image=graph_image,
        colorize=colorize,
        color_thresholds=color_thresholds,
        verbose=bool(verbose),
        radius_correction_factor=radius_correction_factor,
        image_size_mm=mm
    )

def etdrs_graph(
        ves_seg_path: str,
        source_dir: str,
        tmp_dir: str,
        output_dir: str,
        output_mount_dir: str,
        container_name: str,
        faz_code_name_map: dict[str, str],
        color_thresholds: list[float] = None,
        z_dim: int = 64,
        bulge_size: float = 3.0,
        voreen_workspace: str = project_folder + "/voreen/feature-vesselgraphextraction_customized_command_line.vws",
        graph_image: bool = True,
        colorize: str = "continuous",
        verbose: bool = False,
        mm: float = 3.0,
        radius_correction_factor: float = -1.0,
        **kwargs):
    extension = ".nii.gz" if ves_seg_path.endswith(".nii.gz") else "."+ves_seg_path.split(".")[-1]
    image_name = os.path.basename(ves_seg_path).removesuffix(extension)
    if output_dir is None:
        output_dir = os.path.dirname(ves_seg_path)
    else:
        output_dir = output_dir
    outdir = os.path.join(os.path.dirname(ves_seg_path).replace(source_dir, output_dir), image_name.removesuffix(extension))
    os.makedirs(outdir, exist_ok=True)
    docker_work_dir = docker_work_dir_for_output(outdir, output_mount_dir)
    
    if extension == ".nii.gz":
        img_nii: nib.Nifti1Image = nib.load(ves_seg_path)
        ves_seg_3d = img_nii.get_fdata(dtype=np.uint8)
    else:
        ves_seg = np.array(Image.open(ves_seg_path), np.uint8)
        ves_seg_3d = convert_2d_to_3d(ves_seg, z_dim=z_dim)
    
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
            outdir=outdir,
            DOCKER_WORK_DIR=docker_work_dir,
            tmp_dir=tmp_dir,
            bulge_size=bulge_size,
            workspace_file=voreen_workspace,
            container_name=container_name,
            graph_image=graph_image,
            colorize=colorize,
            color_thresholds=color_thresholds,
            verbose=bool(verbose),
            image_size_mm=mm
        )

def perform_graph_feature_extraction(
        tmp_dir: str,
        output_dir: str,
        image_files: str,
        faz_dir: str = None,
        thresholds: str = None,
        voreen_image_name: str="voreen",
        etdrs: bool = False,
        z_dim: int = 64,
        bulge_size: float = 3.0,
        voreen_workspace: str = project_folder + "/voreen/feature-vesselgraphextraction_customized_command_line.vws",
        graph_image: bool = True,
        colorize: str = "continuous",
        verbose: bool = False,
        mm: float = 3.0,
        radius_correction_factor: float = -1.0,
        threads: int = cpu_count() - 1,
        **kwargs
):
    global DOCKER_WORK_DIR, DOCKER_VOREEN_BIN
    output_dir = output_dir or None

    ves_seg_files = [p for p in natsorted(glob.glob(image_files, recursive=True))]
    assert len(ves_seg_files)>0, f"Found no matching vessel segmentation files for path {image_files}!"
    source_dir = os.path.commonpath(ves_seg_files)
    if not os.path.isdir(source_dir):
        source_dir = os.path.dirname(source_dir)
    output_dir = output_dir or source_dir
    ensure_writable_output_dir(output_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    color_thresholds = [float(t) for t in thresholds.split(",")] if thresholds else None

    container_name = None
    # Check if we're running in Docker (DooD setup)
    running_in_docker = os.path.exists("/.dockerenv")
    load_dotenv("/tmp/.env" if running_in_docker else None)
    HOST_OUTPUT_DIR = os.getenv("HOST_OUTPUT_DIR")
    
    # Check if a voreen container from docker compose is already running
    docker_compose_container = None
    client = docker.from_env()
    for container in client.containers.list(filters={"status": "running"}):
        if container.name == "voreen-container":  # docker compose container name
            docker_compose_container = container
            container_name = container.name
            print(f"Found existing docker compose Voreen container: {container_name}")
            break
    
    # Start docker container if not running in docker and no docker compose container found
    if not running_in_docker and docker_compose_container is None:
        # Check if container of this image is running
        client = docker.from_env()
        for container in client.containers.list(filters={"status": "running"}):
            if container.image.tags and any(voreen_image_name in tag for tag in container.image.tags):
                container_name = container.name
                break
        if container_name is None:
            if verbose:
                print(f"No running container for image {voreen_image_name} found. Starting a new container...")
            HOST_OUTPUT_DIR = output_dir # .env file shoudl only be used in DooD setup
            container = client.containers.run(
                image=voreen_image_name,
                detach=True,
                tty=True,
                stdin_open=True,
                command="tail -f /dev/null",
                user=f"{os.getuid()}:{os.getgid()}",
                volumes={
                    tmp_dir: {'bind': "/var/tmp", 'mode': 'rw'},
                    source_dir: {'bind': "/var/src", 'mode': 'ro'},
                    HOST_OUTPUT_DIR: {'bind': DOCKER_WORK_DIR, 'mode': 'rw'}
                },
            )
            container_name = container.name
            # Ensure Voreen can write to its internal data directory
            container.exec_run(user="root", cmd=f"chmod 777 -R {DOCKER_VOREEN_BIN}/../data")
            print(f"Started new Voreen container: {container_name} with volume mapping:\n"
                  f"  - {tmp_dir} <-> /var/tmp\n"
                  f"  - {source_dir} <-> /var/src\n"
                  f"  - {HOST_OUTPUT_DIR} <-> {DOCKER_WORK_DIR}")
    elif running_in_docker:
        if verbose:
            print("Running in Docker container. Using DooD setup to communicate with Voreen container.")
        # In DooD setup, we need to start the Voreen container from within our Python container
        client = docker.from_env()
        for container in client.containers.list(filters={"status": "running"}):
            if container.image.tags and any(voreen_image_name in tag for tag in container.image.tags):
                container_name = container.name
                break
        if container_name is None:
            if verbose:
                print(f"No running container for image {voreen_image_name} found. Starting a new container...")
            container = client.containers.run(
                image=voreen_image_name,
                detach=True,
                tty=True,
                stdin_open=True,
                command="tail -f /dev/null",
                user=f"{os.getuid()}:{os.getgid()}",
                volumes={
                    tmp_dir: {'bind': "/var/tmp", 'mode': 'rw'},
                    source_dir: {'bind': "/var/src", 'mode': 'ro'},
                    HOST_OUTPUT_DIR: {'bind': DOCKER_WORK_DIR, 'mode': 'rw'}
                },
            )
            container_name = container.name
            # Ensure Voreen can write to its internal data directory
            container.exec_run(user="root", cmd=f"chmod 777 -R {DOCKER_VOREEN_BIN}/../data")
            if verbose:
                print(f"Started new Voreen container: {container_name} with volume mapping:\n"
                    f"  - {tmp_dir} -> /var/tmp\n"
                    f"  - {source_dir} -> /var/src\n"
                    f"  - {HOST_OUTPUT_DIR} -> {DOCKER_WORK_DIR}")
        # load_dotenv("/tmp/.env")
        # subfolder = "/" + str(output_dir).removeprefix(os.getenv("HOST_OUTPUT_DIR")).removeprefix("/")
        # print(f"Running in Docker container with subfolder {subfolder}.")
        # DOCKER_WORK_DIR = DOCKER_WORK_DIR + subfolder
    
    output_mount_dir = (
        os.getenv("CONTAINER_OUTPUT_DIR", "/data/output")
        if running_in_docker
        else (HOST_OUTPUT_DIR or output_dir)
    )
    if verbose:
        print(f"Mapping output paths relative to {output_mount_dir}.")

    if etdrs:
        assert bool(faz_dir)
        faz_seg_files = natsorted(glob.glob(f'{faz_dir}/**/*.*', recursive=True))
        assert len(faz_seg_files)>0, f"Found no matching FAZ files at path {faz_dir}! Note, this script currently only supports .png, .jpg, and .bmp faz segmentation files."
        faz_code_name_map = {get_code_name(path): path for path in faz_seg_files if ("dvc" in path.lower()) or ("dcp" in path.lower())}
        task = partial(
            etdrs_graph,
            source_dir=source_dir,
            tmp_dir=tmp_dir,
            output_dir=output_dir,
            output_mount_dir=output_mount_dir,
            container_name=container_name,
            faz_code_name_map=faz_code_name_map,
            color_thresholds=color_thresholds,
            z_dim=z_dim,
            bulge_size=bulge_size,
            voreen_workspace=voreen_workspace,
            graph_image=graph_image,
            colorize=colorize,
            verbose=verbose,
            mm=mm,
            radius_correction_factor=radius_correction_factor
        )
    else:
        task = partial(
            full_graph,
            source_dir=source_dir,
            tmp_dir=tmp_dir,
            output_dir=output_dir,
            output_mount_dir=output_mount_dir,
            container_name=container_name,
            color_thresholds=color_thresholds,
            z_dim=z_dim,
            bulge_size=bulge_size,
            voreen_workspace=voreen_workspace,
            graph_image=graph_image,
            colorize=colorize,
            verbose=verbose,
            mm=mm,
            radius_correction_factor=radius_correction_factor
            )

    if verbose:
        print(f"Using {threads} threads for graph feature extraction.")
    try:
        if threads>1:
            # Multi processing
            with tqdm(total=len(ves_seg_files), desc="Extracting graph features...") as pbar:
                with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
                    future_dict = {executor.submit(task, ves_seg_files[i]): i for i in range(len(ves_seg_files))}
                    for future in concurrent.futures.as_completed(future_dict):
                        future.result()
                        pbar.update(1)
        else:
            # Single processing
            for ves_seg_path in tqdm(ves_seg_files, desc="Extracting graph features..."):
                task(ves_seg_path)
    except Exception as e:
        print(f"An error occurred during graph feature extraction:\n{e}")
        raise
    finally:
        if container_name is not None:
            client = docker.from_env()
            container = client.containers.get(container_name)
            container.stop()
            container.remove()
            print(f"Container '{container_name}' stopped and removed.")


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
    parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=max(1, cpu_count()-1))

    args = parser.parse_args()
    kwargs = vars(args)
    perform_graph_feature_extraction(**kwargs)
