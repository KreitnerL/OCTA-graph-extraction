#!/bin/bash

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ] || [ -z "$1" ]; then
    echo "OCTA Graph Extraction Docker Shell"
    echo "Usage: $0 <mode> [options...]"
    echo ""
    echo "Available modes:"
    echo "  faz_seg               - Perform FAZ (Foveal Avascular Zone) segmentation"
    echo "  graph                 - Extract vessel graphs from segmentation masks"
    echo "  summary               - Generate analysis summary from extracted graphs"
    echo "  pipeline              - Complete pipeline (FAZ segmentation + full graph extraction)"
    echo "  etdrs_pipeline        - Complete ETDRS pipeline (FAZ segmentation + ETDRS graph extraction)"
    echo ""
    echo "Examples:"
    echo "  $0 graph_extraction_full --verbose"
    echo "  $0 etdrs_pipeline --bulge_size 2.5"
    echo "  $0 faz_seg --output_format png"
    echo ""
    echo "Options are passed through to the underlying Python scripts."
    echo "Use '$0 <mode> --help' to see mode-specific options."
    exit 0
fi

echo "[Info] Mode: $1"
mode=$1
shift
source /home/OCTA-graph-extraction/.venv/bin/activate

# Check if we're running in Docker (DooD setup)
if [ -f "/.dockerenv" ]; then
    echo "[Info] Running in Docker container (DooD mode)"
    # Host paths (from compose .env) — for Voreen volume binds and user-facing messages only
    export HOST_TMP_DIR="${HOST_TMP_DIR:-/tmp/voreen}"
    export HOST_OUTPUT_DIR="${HOST_OUTPUT_DIR:-}"
    export HOST_SRC_DIR="${HOST_SRC_DIR:-}"
    # Container mount paths — Python must read/write here inside this container
    OUTPUT_DIR=/data/output
    SRC_DIR=/data/src
    TEMP_DIR=/tmp/voreen

    # Voreen child container needs host paths on the Docker host filesystem
    echo "HOST_TMP_DIR=$HOST_TMP_DIR" > /tmp/.env
    echo "HOST_OUTPUT_DIR=$HOST_OUTPUT_DIR" >> /tmp/.env
    echo "HOST_SRC_DIR=$HOST_SRC_DIR" >> /tmp/.env
else
    echo "[Info] Running on host system"
    TEMP_DIR=/tmp/voreen
    OUTPUT_DIR=/data/output
    SRC_DIR=/data/src
fi

if [ "$mode" = "faz_seg" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR" "$@"
elif [ "$mode" = "graph" ]
then
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR" --tmp_dir "$TEMP_DIR" "$@"
elif  [ "$mode" = "summary" ]
then
    python /home/OCTA-graph-extraction/generate_analysis_summary.py \
        --source_dir "$OUTPUT_DIR/graphs" \
        --output_dir "$OUTPUT_DIR" \
        --faz_files "$OUTPUT_DIR/faz/faz_*.png" \
        --segmentation_dir "$SRC_DIR" \
        "$@"
elif [ "$mode" = "pipeline" ]
then
    python /home/OCTA-graph-extraction/pipeline.py --source_dir "$SRC_DIR" --output_dir "$OUTPUT_DIR" --tmp_dir "$TEMP_DIR" "$@"
else
    echo "Error: Mode '$mode' does not exist."
    echo ""
    echo "Available modes: faz_seg, graph, pipeline, etdrs_pipeline, summary"
    echo "Use '$0 --help' for detailed usage information."
    exit 1
fi