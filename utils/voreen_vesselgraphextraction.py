import os
import h5py
import numpy as np
import docker

DOCKER_TMP_DIR = '/var/tmp'
DOCKER_CACHE_DIR = '/var/cache'
DOCKER_WORK_DIR = '/var/results'
DOCKER_VOREEN_TOOL_PATH = '/home/software/voreen-voreen-5.3.0/voreen/bin/'
# DOCKER_VOREEN_TOOL_PATH = '/home/software/voreen-src-unix-nightly/bin'

def extract_vessel_graph(volume_path: str,
                         outdir: str,
                         tempdir: str,
                         bulge_size: float,
                         workspace_file: str,
                         container_name: str,
                         name='',
                         generate_graph_file=False,
                         verbose=False):
    bulge_size_identifier = f'{bulge_size}'
    bulge_size_identifier = bulge_size_identifier.replace('.','_')

    bulge_path = f'<Property mapKey="minBulgeSize" name="minBulgeSize" value="{bulge_size}"/>'

    if container_name is not None:
        tmp_dir_folder = tempdir.removesuffix("/").split('/')[-1]
        DOCKER_TMP_SUB_DIR = f"{DOCKER_TMP_DIR}/{tmp_dir_folder}"
        volume_path = volume_path.replace(tempdir, DOCKER_TMP_SUB_DIR+"/")
        out_path = f'{DOCKER_TMP_SUB_DIR}/sample.h5'
    else:
        out_path = f'{tempdir}sample.h5'


    bulge_size_identifier = f'{bulge_size}'
    bulge_size_identifier = bulge_size_identifier.replace('.','_')
    edge_path = f'{DOCKER_WORK_DIR}/{name}_edges.csv'
    node_path = f'{DOCKER_WORK_DIR}/{name}_nodes.csv'
    graph_path = f'{DOCKER_WORK_DIR}/{name}_graph.vvg'

    voreen_workspace = 'feature-vesselgraphextraction_customized_command_line.vws'

    # Read in the file
    with open(workspace_file, 'r') as file :
        filedata = file.read()


    # Replace the target string
    filedata = filedata.replace("volume.nii", volume_path)
    filedata = filedata.replace("nodes.csv", node_path)
    filedata = filedata.replace("edges.csv", edge_path)
    filedata = filedata.replace("graph.vvg", graph_path)
    filedata = filedata.replace('<Property mapKey="continousSave" name="continousSave" value="false" /> <Property mapKey="graphFilePath"',
                                f'<Property mapKey="continousSave" name="continousSave" value="{str(generate_graph_file).lower()}" /> <Property mapKey="graphFilePath"')
    filedata = filedata.replace('<Property mapKey="minBulgeSize" name="minBulgeSize" value="3" />', bulge_path)
    filedata = filedata.replace("input.nii", volume_path)
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
        
    if generate_graph_file:
        os.rename(graph_path.replace(DOCKER_WORK_DIR, outdir), graph_path.replace(DOCKER_WORK_DIR, outdir).replace(".vvg", ".json"))
    
    # Make sure all files are written and flushed to disk
    os.sync()

    with h5py.File(out_path.replace(DOCKER_TMP_SUB_DIR + "/", tempdir), "r") as f:
        # Print all root level object names (aka keys) 
        # these can be group or dataset names 
        a_group_key = list(f.keys())[0]
        ds_arr = f[a_group_key][()]  # returns as a numpy array
        os.system(f"rm -rf '{absolute_temp_path}' 2> /dev/null")
    ret = ds_arr[1]
    ret = np.flip(np.rot90(ret),0)
    return ret

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