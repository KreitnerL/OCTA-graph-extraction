import argparse
import os
import nibabel as nib
from PIL import Image
import numpy as np
from utils.voreen_vesselgraphextraction import extract_vessel_graph
from utils.visualizer import node_edges_to_graph
import pathlib
from tqdm import tqdm
import glob
from natsort import natsorted

project_folder = str(pathlib.Path(__file__).parent.resolve())

# You may want to customize these
####################################################################################################
workspace_file = project_folder+"/voreen/feature-vesselgraphextraction_customized_command_line.vws"

# Any empty or non-existing folder with write access
workdir = project_folder+"/voreen/workdir/"
tempdir = project_folder+"/voreen/tmpdir/"
cachedir = project_folder+"/voreen/cachedir/"
####################################################################################################

def extract_graph_features(a: np.ndarray,
                           image_name: str,
                           output_dir: str,
                           bulge_size=5,
                           voreen_tool_path="/home/linus/Software/voreen-src-unix-nightly/bin",
                           graph_image=True,
                           generate_graph_file=False,
                           colorize=False,
                           verbose=False):
    a = np.stack([np.zeros_like(a), a, np.zeros_like(a)], axis=-1)
    img_nii = nib.Nifti1Image(a.astype(np.uint8), np.eye(4))
    
    if not os.path.exists(tempdir):
        os.mkdir(tempdir)
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
        graph_img = node_edges_to_graph(nodes_file, edges_file, a.shape[:2], colorize=colorize)
        Image.fromarray(graph_img.astype(np.uint8)).save(os.path.join(output_dir, f'{image_name}_graph.png'))

if __name__ == "__main__":
    # Parse input arguments
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--image_dir', help="Absolute path to the folder containing all the segmentation maps", type=str, required=True)
    parser.add_argument('--output_dir', help="Absolute path to the folder where the graph and feature files should be stored."
                        +"If no folder is provided, the files will be stored in the same directory as the source images.", type=str, default=None)
    parser.add_argument('--voreen_tool_path', help="Absolute path to the bin folder of your voreen installation", type=str, default="/home/shared/Software/Voreen-source/bin/")
    parser.add_argument('--bulge_size', help="Numeric value of the bulge_size parameter to control the sensitivity", type=float, default=5)

    parser.add_argument('--graph_image', help="Generate an image of the extracted graph", type=bool, default=True)
    parser.add_argument('--colorize_graph', help="Generate colored radius graph", type=bool, default=False)
    parser.add_argument('--generate_graph_file', help="Generate the graph JSON file", type=bool, default=False)
    parser.add_argument('--verbose', action="store_true", help="Print log information from voreen")


    args = parser.parse_args()

    image_paths = natsorted(glob.glob(args.image_dir+"/*.png"))
    for image_path in tqdm(image_paths, desc="Extracting graph features"):
        output_dir = '/'.join(image_path.split('/')[:-1])
        if args.output_dir is not None:
            output_dir = output_dir.replace(args.image_dir, args.output_dir)
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)
        image_name = '.'.join(image_path.split("/")[-1].split(".")[:-1])
        a = np.array(Image.open(image_path))
        extract_graph_features(a, image_name, output_dir, args.bulge_size, args.voreen_tool_path, args.graph_image, args.generate_graph_file, args.colorize_graph, verbose=bool(args.verbose))