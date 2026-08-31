import glob
import math
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

CONTAINER_OUTPUT_DIR = os.environ.get("CONTAINER_OUTPUT_DIR", "/data/output")
CONTAINER_SRC_DIR = os.environ.get("CONTAINER_SRC_DIR", "/data/src")
VOREEN_BIOMARKERS = [
    "length",
    "distance",
    "curveness",
    "volume",
    "avgCrossSection",
    "minRadiusAvg",
    "minRadiusStd",
    "avgRadiusAvg",
    "avgRadiusStd",
    "maxRadiusAvg",
    "maxRadiusStd",
    "roundnessAvg",
    "roundnessStd",
]
ALLOWED_BIOMARKERS = ["density", *VOREEN_BIOMARKERS]


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


def display_path(path: str) -> str:
    """Map container mount paths to host paths for user-facing messages."""
    path = os.path.abspath(path)
    host_out = os.environ.get("HOST_OUTPUT_DIR")
    host_src = os.environ.get("HOST_SRC_DIR")
    if host_out and path.startswith(CONTAINER_OUTPUT_DIR):
        return os.path.join(host_out, os.path.relpath(path, CONTAINER_OUTPUT_DIR))
    if host_src and path.startswith(CONTAINER_SRC_DIR):
        return os.path.join(host_src, os.path.relpath(path, CONTAINER_SRC_DIR))
    return path


def graph_group_relpath(data_file: str, graph_root: str, etdrs: bool) -> str:
    """Return the graph output subfolder that should correspond to a segmentation group."""
    rel_parts = os.path.relpath(data_file, graph_root).split(os.sep)
    group_parts = rel_parts[:-2] if etdrs else rel_parts[:-1]
    return os.path.join(*group_parts) if group_parts else "."


def segmentation_group(seg_file: str, segmentation_root: str) -> str:
    """Return a stable group name from the matched segmentation path."""
    rel_parent = os.path.dirname(os.path.relpath(seg_file, segmentation_root))
    if rel_parent in ("", "."):
        return os.path.basename(os.path.abspath(segmentation_root))
    return rel_parent.split(os.sep)[0]


def find_matching_segmentation(
        data_file: str,
        image_id: str,
        source_dir: str,
        segmentation_dir: str,
        segmentation_files: list[str],
        etdrs: bool,
) -> str | None:
    candidates = [
        f for f in segmentation_files
        if remove_prefixes(remove_extensions(os.path.basename(f))) == image_id
    ]
    if not candidates:
        return None
    graph_group = graph_group_relpath(data_file, source_dir, etdrs)
    if graph_group != ".":
        for candidate in candidates:
            seg_rel_parent = os.path.dirname(os.path.relpath(candidate, segmentation_dir))
            if seg_rel_parent == graph_group or seg_rel_parent.startswith(graph_group + os.sep):
                return candidate
    return candidates[0]


def parse_radius_thresholds(radius_thresholds: str) -> tuple[list[float], bool]:
    """
    Parse radius threshold string.
    Returns (threshold_values, single_bin) where single_bin=True means one density column for all radii.
    """
    if not radius_thresholds or not str(radius_thresholds).strip():
        return [], True
    thresholds = []
    for token in radius_thresholds.split(","):
        token = token.strip().lower()
        if not token:
            continue
        thresholds.append(float("inf") if token == "inf" else float(token))
    if len(thresholds) >= 2 and thresholds[0] == 0.0 and math.isinf(thresholds[-1]):
        if len(thresholds) == 2:
            return [], True
    return thresholds, False


def parse_biomarkers(biomarkers: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Parse and validate requested analysis biomarkers."""
    if biomarkers is None or biomarkers == "":
        return ["density"]
    if isinstance(biomarkers, str):
        parsed = [token.strip() for token in biomarkers.split(",") if token.strip()]
    else:
        parsed = []
        for item in biomarkers:
            parsed.extend(token.strip() for token in str(item).split(",") if token.strip())
    parsed = parsed or ["density"]

    invalid = [biomarker for biomarker in parsed if biomarker not in ALLOWED_BIOMARKERS]
    if invalid:
        raise ValueError(
            f"Unsupported biomarker(s): {', '.join(invalid)}.\n"
            f"Allowed biomarkers: {', '.join(ALLOWED_BIOMARKERS)}"
        )

    unique = []
    for biomarker in parsed:
        if biomarker not in unique:
            unique.append(biomarker)
    return unique


def validate_summary_inputs(
        source_dir: str,
        segmentation_dir: str,
        edge_files: list[str],
        segmentation_files: list[str],
        faz_shape: tuple[int, int] | None,
) -> None:
    source_dir = os.path.abspath(source_dir)
    segmentation_dir = os.path.abspath(segmentation_dir)

    graphs_subdir = os.path.join(source_dir, "graphs")
    if (
        os.path.basename(source_dir.rstrip(os.sep)) != "graphs"
        and os.path.isdir(graphs_subdir)
        and glob.glob(os.path.join(graphs_subdir, "**/*_edges.csv"), recursive=True)
    ):
        raise ValueError(
            f"--source_dir must point to the graphs folder (containing *_edges.csv and *_graph.json), "
            f"not the pipeline output root.\n"
            f"  You passed: {display_path(source_dir)}\n"
            f"  Use instead: {display_path(graphs_subdir)}"
        )

    if not segmentation_files:
        raise ValueError(
            f"No segmentation PNG files found under --segmentation_dir:\n"
            f"  {display_path(segmentation_dir)}\n"
            f"This must be the vessel segmentation folder (same path as pipeline --source_dir), "
            f"not the output root with faz/, graphs/, or raw images/."
        )

    sample_names = [os.path.basename(f) for f in segmentation_files[:50]]
    if any(name.startswith("faz_") for name in sample_names):
        raise ValueError(
            f"--segmentation_dir must contain vessel segmentation maps only.\n"
            f"  You passed: {display_path(segmentation_dir)}\n"
            f"Found faz_*.png files here. Point --segmentation_dir at your segmentations folder "
            f"(and --source_dir at .../graphs under the pipeline output)."
        )
    if any("_graph.png" in name for name in sample_names):
        raise ValueError(
            f"--segmentation_dir must not contain graph visualization PNGs.\n"
            f"  You passed: {display_path(segmentation_dir)}\n"
            f"Use the segmentations folder for --segmentation_dir and .../graphs for --source_dir."
        )

    seg_shapes = {Image.open(f).size for f in segmentation_files[:20]}
    if len(seg_shapes) > 1:
        raise ValueError(
            f"Segmentation images under {display_path(segmentation_dir)} have inconsistent sizes: {seg_shapes}."
        )
    seg_shape = next(iter(seg_shapes))
    if faz_shape and seg_shape != faz_shape:
        raise ValueError(
            f"FAZ mask size {faz_shape} does not match segmentation size {seg_shape}.\n"
            f"  FAZ folder vs segmentations folder may be mismatched."
        )

    # Probe first graph/segmentation pair for render vs mask size
    data_file = edge_files[0]
    if "_edges.csv" in os.path.basename(data_file):
        image_id = remove_prefixes(remove_extensions(os.path.basename(data_file).replace("_edges.csv", "")))
        seg_file = next(
            (f for f in segmentation_files if remove_prefixes(remove_extensions(os.path.basename(f))) == image_id),
            None,
        )
        if seg_file:
            seg_h = Image.open(seg_file).size[1]
            render_dim = faz_shape[0] if faz_shape else seg_h
            if seg_h != render_dim:
                raise ValueError(
                    f"Graph render dimension ({render_dim}px) does not match segmentation ({seg_h}px) "
                    f"for sample '{image_id}'.\n"
                    f"  --segmentation_dir: {display_path(segmentation_dir)}\n"
                    f"  Matched segmentation: {display_path(seg_file)}\n"
                    f"Check that --segmentation_dir is the vessel segmentation folder, not raw OCTA images "
                    f"or the pipeline output root."
                )


def generate_biomarker_title(area: str, biomarker: str, lower: int, upper: int) -> str:
    """Generate output column title based on area, biomarker, and radius thresholds."""
    display_name = "Density" if biomarker == "density" else biomarker
    title = f"{area} {display_name} ("
    if lower is not None:
        title += f"{lower}um < "
    title += "radius"
    if upper is not None:
        title += f" < {upper}um"
    title += ") [%]"
    if biomarker != "density":
        title = title.removesuffix(" [%]")
    return title


def edge_radius_mm_by_id(graph_json: pd.DataFrame, edges_df: pd.DataFrame, dim: int, image_size_mm: float) -> dict[int, float]:
    """Compute each edge's median rendered radius in millimeters, matching density stratification."""
    radii = {}
    for edge in graph_json["graph"]["edges"]:
        edge_id = edge["id"]
        if edge_id not in edges_df.index:
            continue
        edge_radii = [
            v["minDistToSurface"] / dim
            for v in edge.get("skeletonVoxels", [])
            if math.isfinite(v["minDistToSurface"])
        ]
        radii[edge_id] = (np.median(edge_radii) if edge_radii else 0) * image_size_mm
    return radii


def biomarker_values_by_interval(edge_df: pd.DataFrame, edge_radii_mm: dict[int, float], biomarker: str, radius_intervals: list[tuple[float, float]]) -> list[float]:
    """Aggregate a Voreen edge biomarker by radius interval."""
    if edge_df.empty:
        return [nan for _ in radius_intervals]
    values = []
    for lower, upper in radius_intervals:
        edge_ids = [
            edge_id for edge_id, radius_mm in edge_radii_mm.items()
            if lower <= radius_mm <= upper
        ]
        if not edge_ids:
            values.append(nan)
            continue
        values.append(edge_df.loc[edge_ids, biomarker].mean())
    return values


def process_file_pair(args_tuple):
    """Process a single file pair for parallel execution."""
    (data_file, graph_file, source_dir, segmentation_dir, segmentation_files, faz_map, AREA_FACTOR_MAP, biomarkers,
     THRESHOLDS, radius_intervals, args_etdrs, args_mm, args_radius_correction_factor, faz_shape) = args_tuple
    
    edge_df = pd.read_csv(data_file, sep=';', index_col=0)
    graph_json = pd.read_json(graph_file, orient='records')

    # Parse file path to extract metadata
    if args_etdrs:
        image_ID, name = data_file.split("/")[-2:]
    else:
        name = data_file.split("/")[-1]
        image_ID = remove_extensions(name)
    image_ID = remove_prefixes(image_ID)

    # Find the corresponding segmentation file before assigning group metadata.
    seg_file = find_matching_segmentation(
        data_file, image_ID, source_dir, segmentation_dir, segmentation_files, args_etdrs
    )
    if seg_file is None:
        raise FileNotFoundError(f"No segmentation file found for {data_file} with code {image_ID}!")
    group = segmentation_group(seg_file, segmentation_dir)
    
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
        
        # Initialize all requested analysis columns with NaN
        for a in AREA_FACTOR_MAP.keys():
            for i in range(len(THRESHOLDS)-1):
                for biomarker in biomarkers:
                    dd[generate_biomarker_title(a, biomarker, THRESHOLDS[i], THRESHOLDS[i+1])] = nan
        new_entry = True
    else:
        dd = {}
        new_entry = False

    seg_img = np.array(Image.open(seg_file), np.float32)/255

    render_dim = faz_shape[0] if faz_shape else seg_img.shape[0]
    if "density" in biomarkers:
        graph_images = []
        for t in radius_intervals:
            graph_img_filtered_t = generate_image_from_graph_json(
                graph_json=graph_json, edges_df=edge_df, radius_interval=t,
                dim=render_dim, image_size_mm=args_mm, colorize="white", radius_correction_factor=args_radius_correction_factor
            ).astype(np.float32) / 255
            try:
                graph_img_filtered_t = graph_img_filtered_t * seg_img
            except ValueError as exc:
                if "broadcast" in str(exc).lower() and "shape" in str(exc).lower():
                    raise ValueError(
                        f"Segmentation shape {seg_img.shape} does not match graph render shape "
                        f"{graph_img_filtered_t.shape} for '{data_file}'.\n"
                        f"  Segmentation file: {display_path(seg_file)}\n"
                        f"  --segmentation_dir must be the vessel segmentation folder (same as pipeline "
                        f"--source_dir), not the output root or raw images/ folder."
                    ) from exc
                raise
            graph_images.append(graph_img_filtered_t)

        # Normalize overlapping pixels and calculate densities
        graph_img = np.stack(graph_images, axis=-1).sum(-1)
        densities = []
        for img in graph_images:
            mask = (graph_img > 0) & (img > 0)
            img[mask] /= graph_img[mask]
            densities.append(img.sum() / area_factor * 100)

        for i in range(len(THRESHOLDS)-1):
            title = generate_biomarker_title(area, "density", THRESHOLDS[i], THRESHOLDS[i+1])
            dd[title] = densities[i] if edge_df.shape[0] > 0 else 0

    edge_biomarkers = [biomarker for biomarker in biomarkers if biomarker != "density"]
    if edge_biomarkers:
        missing_columns = [biomarker for biomarker in edge_biomarkers if biomarker not in edge_df.columns]
        if missing_columns:
            raise ValueError(
                f"Requested biomarker(s) missing from {display_path(data_file)}: {', '.join(missing_columns)}"
            )
        edge_radii_mm = edge_radius_mm_by_id(graph_json, edge_df, render_dim, args_mm)
        for biomarker in edge_biomarkers:
            values = biomarker_values_by_interval(edge_df, edge_radii_mm, biomarker, radius_intervals)
            for i, value in enumerate(values):
                title = generate_biomarker_title(area, biomarker, THRESHOLDS[i], THRESHOLDS[i+1])
                dd[title] = value
    
    return dd, new_entry, area

def generate_anylsis_file(
        source_dir: str,
        segmentation_dir: str,
        output_dir: str = None,
        faz_files: str = None,
        radius_thresholds: str = "",
        mm: float = 3.0,
        etdrs: bool = False,
        center_radius: float = 3/6,
        inner_radius: float = 3/2.4,
        radius_correction_factor: float = -1.0,
        biomarkers: str | list[str] | tuple[str, ...] | None = "density",
        threads: int = cpu_count() - 1,
        **kwargs
):
    biomarkers = parse_biomarkers(biomarkers)
    # Find and validate input files
    edge_files = natsorted(glob.glob(os.path.join(source_dir, "**/*_edges.csv"), recursive=True))
    graph_files = natsorted(glob.glob(os.path.join(source_dir, "**/*_graph.json"), recursive=True))
    segmentation_files = natsorted(glob.glob(os.path.join(segmentation_dir, "**/*.png"), recursive=True))
    assert edge_files, (
        f"No '_edges.csv' files found under --source_dir:\n"
        f"  {display_path(source_dir)}\n"
        f"Point --source_dir at the graphs folder (e.g. <output_dir>/graphs) produced by graph extraction."
    )
    assert graph_files, (
        f"No '_graph.json' files found under --source_dir:\n"
        f"  {display_path(source_dir)}"
    )

    # Process FAZ files if provided
    faz_map = {}
    faz_shape = None
    if faz_files:
        faz_paths = natsorted(glob.glob(faz_files, recursive=True))
        if not faz_paths:
            print(f"No FAZ files matched pattern: {faz_files}")
        for faz_file in tqdm(faz_paths, desc="Processing FAZ files"):
            faz = np.array(Image.open(faz_file))
            if faz_shape is None:
                faz_shape = faz.shape[:2]
            image_area = faz.shape[0] * faz.shape[1]
            faz_area = (faz/255).sum() / image_area * mm**2
            faz_map[code_name(faz_file)] = faz_area

    validate_summary_inputs(
        source_dir, segmentation_dir, edge_files, segmentation_files, faz_shape
    )

    # Setup area masks and factors
    if etdrs:
        assert faz_map, "FAZ files are required for ETDRS analysis!"
        faz_sample = np.array(Image.open(faz_paths[0]))
        center_mask, q1_mask, q2_mask, q3_mask, q4_mask = get_ETDRS_grid_masks(
            np.ones_like(faz_sample),
            center_radius=center_radius/mm*faz_sample.shape[0],
            inner_radius=inner_radius/mm*faz_sample.shape[0]
        )
        AREA_FACTOR_MAP = {"C0": center_mask.sum(), "S1": q1_mask.sum(), "N1": q2_mask.sum(), "I1": q3_mask.sum(), "T1": q4_mask.sum()}
    else:
        ref = np.array(Image.open(segmentation_files[0]))
        AREA_FACTOR_MAP = {"": ref.shape[0] * ref.shape[1]}

    thresholds, single_radius_bin = parse_radius_thresholds(radius_thresholds)
    if single_radius_bin:
        THRESHOLDS = [None, None]
        radius_intervals = [(0, np.inf)]
    else:
        THRESHOLDS = [None, *thresholds, None]
        radius_intervals = list(zip(
            [0] + [t / 1000 for t in thresholds],
            [t / 1000 for t in thresholds] + [np.inf],
        ))

    # Prepare arguments for parallel processing
    process_args = []
    for data_file, graph_file in zip(edge_files, graph_files):
        args_tuple = (
            data_file, graph_file, source_dir, segmentation_dir, segmentation_files, faz_map, AREA_FACTOR_MAP, biomarkers,
            THRESHOLDS, radius_intervals, etdrs, mm, radius_correction_factor, faz_shape,
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
    if biomarkers == ["density"]:
        output_name = "density_measurements_etdrs.csv" if etdrs else "density_measurements_full.csv"
    elif len(biomarkers) == 1:
        output_name = f"{biomarkers[0]}_measurements_etdrs.csv" if etdrs else f"{biomarkers[0]}_measurements_full.csv"
    else:
        output_name = "analysis_measurements_etdrs.csv" if etdrs else "analysis_measurements_full.csv"
    output_path = os.path.join(output_dir, output_name)
    df.to_csv(output_path, index=False, sep=",")
    print(f"Analysis summary saved to {display_path(output_path)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate analysis summary from OCTA graph data.')
    parser.add_argument('--source_dir', type=str, help="Absolute path to the folder graph features", required=True)
    parser.add_argument('--segmentation_dir', type=str, help="Absolute path to the segmentation maps", required=True)

    parser.add_argument('--output_dir', type=str, help="Absolute path to the output folder. If none is given, save in source folder.")
    parser.add_argument('--faz_files', type=str, help="Absolute path to the faz segmentation files. Required for etdrs analysis.")
    
    parser.add_argument(
        '--radius_thresholds',
        type=str,
        default="",
        help="Comma-separated radius thresholds [um] for stratified density columns (e.g. '5,10,15'). "
             "Omit or leave empty for a single density column over all radii.",
    )
    parser.add_argument(
        '--biomarkers',
        type=str,
        default="density",
        help=f"Comma-separated biomarkers to summarize. Allowed: {', '.join(ALLOWED_BIOMARKERS)}. Default: density.",
    )
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
