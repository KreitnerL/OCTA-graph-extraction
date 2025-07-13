import os
import h5py
import numpy as np
import docker
import nibabel as nib
import pandas as pd
import uuid
from typing import Literal
from utils.visualizer import generate_image_from_graph_json
from PIL import Image

DOCKER_TMP_DIR = '/var/tmp'
DOCKER_CACHE_DIR = '/var/cache'
DOCKER_VOREEN_TOOL_PATH = '/home/software/voreen-voreen-5.3.0/voreen/bin/'
# DOCKER_VOREEN_TOOL_PATH = '/home/software/voreen-src-unix-nightly/bin'

def _sanity_filter(df_rows: pd.DataFrame, df_nodes: pd.DataFrame, z_dim, lower_z=0.3, upper_z=0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_rows_filtered = df_rows[
        (df_rows.volume>0) & (df_rows.distance>0) & (df_rows.curveness>0) & (df_rows.avgRadiusAvg>0) & (df_rows.avgRadiusStd)
    ]
    return df_rows_filtered, df_nodes

def extract_vessel_graph(
        img_nii: nib.nifti1.Nifti1Image,
        image_name: str,
        outdir: str,
        DOCKER_WORK_DIR: str,
        tmp_dir: str,
        bulge_size: float,
        workspace_file: str,
        container_name: str,
        graph_image: bool = True,
        colorize: Literal["continuous", "thresholds", "random", "white"] = "continuous",
        color_thresholds: list[float] = None,
        verbose=False,
        radius_correction_factor: float = -1.0,
        image_size_mm: float = 3.0
    ):
    """
    Extracts a vessel graph from a NIFTI image using Voreen's vessel graph extraction tool and stores the results in the specified output directory.
    Args:
        img_nii (nib.nifti1.Nifti1Image): The input NIFTI image containing the OCTA data.
        image_name (str): The name of the image file (without extension).
        outdir (str): Directory where the output files will be saved.
        tempdir (str): Temporary directory for intermediate files.
        bulge_size (float): Minimum size of a bulge in the vessel graph.
        workspace_file (str): Path to the Voreen workspace file.
        container_name (str): Name of the Docker container to run the Voreen tool in.
        graph_image (bool): Whether to generate a graph image from the extracted vessel graph.
        colorize (Literal["continuous", "thresholds", "random", "white"]): Specifies how to color the edges in the graph image.
            - "continuous": Color edges based on their radius, using a continuous color map.
            - "thresholds": Color edges based on the given thresholds.
            - "random": Assign a random color to each segment.
            - "white": Use a default color (white).
        color_thresholds (list[float]): A list of thresholds for coloring edges when `colorize` is set to "thresholds". 
            This should be provided as a list of floats
        verbose (bool): Whether to print verbose output.
        radius_correction_factor (float): Additive correction factor for the radius estimation. Default is -1.0 to correct for Voreen's overestimation by 1 pixel measured on synthetic data.
        image_size_mm (float): The size of the image in millimeters, used for scaling.

    Returns:
        np.ndarray: The extracted vessel graph as a NumPy array.
    Raises:
        Exception: If the graph file is not found after extraction.
    """
    while True:
        tempdir = f"{tmp_dir}/{str(uuid.uuid4())}/"
        if not os.path.isdir(tempdir):
            break
    os.makedirs(tempdir)
    volume_path = os.path.join(tempdir, f'{image_name}.nii')
    nib.save(img_nii, volume_path)

    bulge_size_identifier = f'{bulge_size}'
    bulge_size_identifier = bulge_size_identifier.replace('.','_')

    bulge_path = f'<Property mapKey="minBulgeSize" name="minBulgeSize" value="{bulge_size}"/>'

    if container_name is not None:
        tmp_dir_folder = tempdir.removesuffix("/").split('/')[-1]
        DOCKER_TMP_SUB_DIR = f"{DOCKER_TMP_DIR}/{tmp_dir_folder}"
        # Use container paths for Voreen commands
        docker_volume_path = volume_path.replace(tmp_dir, DOCKER_TMP_DIR)
        out_path = f'{DOCKER_TMP_SUB_DIR}/sample.h5'
    else:
        docker_volume_path = volume_path
        out_path = f'{tempdir}sample.h5'

    bulge_size_identifier = f'{bulge_size}'
    bulge_size_identifier = bulge_size_identifier.replace('.','_')
    edge_path = f'{DOCKER_WORK_DIR}/{image_name}_edges.csv'
    node_path = f'{DOCKER_WORK_DIR}/{image_name}_nodes.csv'
    graph_path = f'{DOCKER_WORK_DIR}/{image_name}_graph.vvg'

    voreen_workspace = 'feature-vesselgraphextraction_customized_command_line.vws'

    # Read in the file
    with open(workspace_file, 'r') as file :
        filedata = file.read()


    # Replace the target string
    filedata = filedata.replace("volume.nii", docker_volume_path if container_name else volume_path)
    filedata = filedata.replace("nodes.csv", node_path)
    filedata = filedata.replace("edges.csv", edge_path)
    filedata = filedata.replace("graph.vvg", graph_path)
    filedata = filedata.replace('<Property mapKey="minBulgeSize" name="minBulgeSize" value="3" />', bulge_path)
    filedata = filedata.replace("input.nii", docker_volume_path if container_name else volume_path)
    filedata = filedata.replace("output.h5", out_path)

    # Write the file out again
    with open(os.path.join(tempdir,voreen_workspace), 'w') as file:
        file.write(filedata)
        file.flush()

    workspace_file = os.path.join(tempdir,voreen_workspace)

    absolute_temp_path = os.path.join(tempdir)

    if container_name is None:
        # extract graph and delete temp directory
        os.system(f'cd {DOCKER_VOREEN_TOOL_PATH} ; ./voreentool \
            --workspace {workspace_file} \
            -platform minimal --trigger-volumesaves --trigger-geometrysaves  --trigger-imagesaves \
            --workdir {outdir} --tempdir {tempdir} --cachedir {DOCKER_CACHE_DIR}' + ("" if verbose else "--logLevel error >/dev/null 2>&1")
        )
    else:
        # Run the command in the docker container
        client = docker.from_env()
        container = client.containers.get(container_name)
        command = f"cd {DOCKER_VOREEN_TOOL_PATH} ; ./voreentool \
            --workspace {DOCKER_TMP_SUB_DIR}/{voreen_workspace} \
            -platform minimal --trigger-volumesaves --trigger-geometrysaves  --trigger-imagesaves \
            --workdir {DOCKER_WORK_DIR} --tempdir {DOCKER_TMP_SUB_DIR} --cachedir {DOCKER_CACHE_DIR}" + ("" if verbose else " --logLevel error >/dev/null 2>&1")
        exec_command = f"/bin/bash -c \"{command}\""
        result = container.exec_run(user=str(os.getuid()), cmd=exec_command, detach=False, stream=True)
        for line in result.output:
            print(line.decode(), end='')
        # Reset terminal formatting after container execution
        print('\033[0m', end='', flush=True)
    try:
        graph_host_path = graph_path.replace(DOCKER_WORK_DIR, outdir)
        os.rename(graph_host_path, graph_host_path.replace(".vvg", ".json"))
        # Make sure all files are written and flushed to disk
        os.sync()

        h5_file_path = out_path.replace(DOCKER_TMP_SUB_DIR + "/", tempdir) if container_name else out_path
        with h5py.File(h5_file_path, "r") as f:
            # Print all root level object names (aka keys) 
            # these can be group or dataset names 
            a_group_key = list(f.keys())[0]
            ds_arr = f[a_group_key][()]  # returns as a numpy array
            os.system(f"rm -rf '{absolute_temp_path}' 2> /dev/null")
        ret = ds_arr[1]
        ret = np.flip(np.rot90(ret),0)

        edges_file = os.path.join(outdir, f'{image_name}_edges.csv')
        nodes_file = os.path.join(outdir, f'{image_name}_nodes.csv')

        # Clean with sanity checks
        df_edges = pd.read_csv(edges_file, sep=";", index_col=0)
        df_nodes = pd.read_csv(nodes_file, sep=";", index_col=0)
        df_edges, df_nodes = _sanity_filter(df_edges,df_nodes, z_dim=img_nii.shape[2])
        df_edges.to_csv(edges_file, sep=";")
        # flush the files to disk
        os.sync()

        if graph_image:
            graph_json = pd.read_json(os.path.join(outdir, f'{image_name}_graph.json'), orient="records")
            img = generate_image_from_graph_json(
                graph_json,
                df_edges,
                dim=img_nii.shape[0],
                image_size_mm=image_size_mm,
                colorize=colorize,
                color_thresholds=color_thresholds,
                radius_correction_factor=radius_correction_factor
            )
            segmentation_2d_mask = img_nii.get_fdata().max(axis=2).astype(np.uint8) // 255
            Image.fromarray(img * segmentation_2d_mask[...,np.newaxis]).save(os.path.join(outdir, f'{image_name}_graph.png'))

        return ret
    except FileNotFoundError as e:
        error_msg = f"{e}\nThere was likely an error during the graph extraction process. Please check the logs for more information using '--verbose --threads 1'"
        print(f"\033[91m{error_msg}\033[0m")
        raise Exception(error_msg)
    

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Control script for running coreen on a headless machine.')
    parser.add_argument('-i','--input_image', help='Specify input file path of a NIFTI image.', required=True)
    parser.add_argument('-b','--bulge_size',help='Specify bulge size',required=True)
    parser.add_argument('-vp','--voreen_tool_path',help="Specify the path where voreentool is located.",default='/home/shared/Software/Voreen-source/bin')
    parser.add_argument('-wp','--workspace_file',default='/home/lkreitner/OCTA-seg/voreen/feature-vesselgraphextraction_customized_command_line.vws')

    parser.add_argument('-wd','--outdir', help='Specify the working directory.', required=True)
    parser.add_argument('-td','--tempdir', help='Specify the temporary data directory.', required=True)
    parser.add_argument('-cd','--cachedir', help='Specify the cache directory.', required=True)
    args = vars(parser.parse_args())

    extract_vessel_graph(args['input_image'], args['outdir'], args['tempdir'], args['cachedir'], float(args['bulge_size']), args['workspace_file'], args['voreen_tool_path'])