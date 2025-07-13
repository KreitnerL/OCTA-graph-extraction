ARG NUMBER_OF_PROCESSES

FROM astral/uv:0.7-python3.13-bookworm-slim

# Install Docker CLI (needed for Docker outside of Docker)
RUN apt-get update && apt-get install -y docker.io ffmpeg libsm6 libxext6 && rm -rf /var/lib/apt/lists/*

# Copy repository files to image directory
COPY . /home/OCTA-graph-extraction

# Install dependencies
WORKDIR /home/OCTA-graph-extraction
RUN uv sync

RUN chmod 755 /home/OCTA-graph-extraction/docker/dockershell.sh
RUN echo "Successfully build image!"
