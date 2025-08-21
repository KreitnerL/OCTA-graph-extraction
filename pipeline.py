
import argparse
import os
import pathlib
from multiprocessing import cpu_count

from dotenv import load_dotenv

from faz_segmentation import perform_faz_segmentation
from generate_analysis_summary import generate_anylsis_file
from graph_feature_extractor import perform_graph_feature_extraction

load_dotenv()
project_folder = str(pathlib.Path(__file__).parent.resolve())

parser = argparse.ArgumentParser(description='Generate analysis summary from OCTA graph data.')

parser.add_argument('--source_dir', type=str, help="Absolute path to the folder graph features", required=True)
parser.add_argument('--tmp_dir', help="Absolute path to the temporary directory where voreen will store its temporary files", type=str, default=os.getenv("DOCKER_TMP_DIR", "/var/tmp"))
parser.add_argument('--output_dir', help="Absolute path to the folder where the graph and feature files should be stored."
                        +"If no folder is provided, the files will be stored in the same directory as the source images.", type=str, default=None)
parser.add_argument('--voreen_image_name', help="Absolute path to the bin folder of your voreen installation", type=str, default="voreen")

parser.add_argument('--voreen_workspace', help="Absolute path to the voreen workspace file", type=str, default=project_folder+"/voreen/feature-vesselgraphextraction_customized_command_line.vws")
parser.add_argument('--bulge_size', help="Numeric value of the bulge_size parameter to control the sensitivity", type=float, default=3)
parser.add_argument('--graph_image', help="Generate an image of the extracted graph", action="store_true", default=True)
parser.add_argument('--no_graph_image', help="Do not generate an image of the extracted graph", action="store_false", dest="colorize_graph")
parser.add_argument('--colorize', help="Generate colored radius graph", choices=["continuous", "thresholds", "random", "white"], default="continuous")
parser.add_argument('--generate_graph_file', help="Generate the graph JSON file", action="store_true", default=True)
parser.add_argument('--no_generate_graph_file', help="Do not generate the graph JSON file", action="store_false", dest="generate_graph_file")
parser.add_argument('--z_dim', help="Z dimension of the 3D segmentation mask. Only needed for 2D segmentation masks.", type=int, default=64)

parser.add_argument('--radius_correction_factor', help="Additive correction factor for the radius estimation. Default is -1.0 to correct for Voreen's overestimation by 1 pixel measured on synthetic data.", type=float, default=-1.0)
parser.add_argument('--radius_thresholds', type=str, default="0,inf", help="Comma separated list of thresholds for vessel stratification [um].")
parser.add_argument('--mm', type=float, default=3.0, help="Height of the segmentation volume in mm. Default is 3 mm")
parser.add_argument('--etdrs', action="store_true", help="If set, use ETDRS grid stratification")
parser.add_argument('--center_radius', type=float, default=3/6, help="Radius of ETDRS center radius in mm")
parser.add_argument('--inner_radius', type=float, default=3/2.4, help="Radius of ETDRS center radius in mm")

parser.add_argument('--verbose', action="store_true", help="Print log information from voreen")
parser.add_argument('--threads', help="Number of parallel threads. By default all available threads but one are used.", type=int, default=cpu_count()-1)
args = parser.parse_args()

source_files = args.source_dir + "/*.png"

perform_faz_segmentation(
    source_files=source_files,
    output_dir=args.output_dir + "/faz",
    threads=args.threads
)

perform_graph_feature_extraction(
    tmp_dir=args.tmp_dir,
    output_dir=args.output_dir+"/graphs",
    image_files=source_files,
    faz_dir=args.output_dir+"/faz",
    thresholds=args.radius_thresholds,
    voreen_image_name=args.voreen_image_name,
    voreen_workspace=args.voreen_workspace,
    bulge_size=args.bulge_size,
    graph_image=args.colorize_graph,
    colorize=args.colorize,
    generate_graph_file=args.generate_graph_file,
    z_dim=args.z_dim,
    etdrs=args.etdrs,
    mm=args.mm,
    radius_thresholds=args.radius_thresholds,
    center_radius=args.center_radius,
    inner_radius=args.inner_radius,
    verbose=args.verbose,
    radius_correction_factor=args.radius_correction_factor,
    threads=args.threads
)

generate_anylsis_file(
    source_dir=args.output_dir+"/graphs",
    segmentation_dir=args.source_dir,
    output_dir=args.output_dir,
    faz_files= args.output_dir+"/faz/*.png",
    radius_thresholds=args.radius_thresholds,
    mm=args.mm,
    etdrs=args.etdrs,
    radius_correction_factor=args.radius_correction_factor,
    center_radius=args.center_radius,
    inner_radius=args.inner_radius,
    threads=args.threads
)
