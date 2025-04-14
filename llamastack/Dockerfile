# Use an official Python base image
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --upgrade pip

# Set working directory
WORKDIR /app

# Clone your repo and checkout the branch
RUN git clone https://github.com/jhpiedrahitao/llama-stack.git && \
    cd llama-stack && \
    git checkout feat/litellm_sambanova_usage

# create environment 
RUN python -m venv /app/llama-stack/.venv
ENV PATH="/app/llama-stack/.venv/bin:$PATH"
RUN /app/llama-stack/.venv/bin/pip install --upgrade pip 
RUN /app/llama-stack/.venv/bin/pip install uv
RUN /app/llama-stack/.venv/bin/pip install -e /app/llama-stack
RUN /app/llama-stack/.venv/bin/pip install -e /app/llama-stack[dev,test]
RUN /app/llama-stack/.venv/bin/pip install -e /app/llama-stack
RUN /app/llama-stack/.venv/bin/pip install litellm faiss-cpu

# Set env vars
ENV UV_SYSTEM_PYTHON=1
ENV LLAMA_STACK_PORT=8321

# Create .llama directory
RUN mkdir -p ~/.llama

# Build the llama stack image
RUN llama stack build --template sambanova --image-type venv

# Remove api_key line from the generated yaml
RUN sed -i '/SAMBANOVA_API_KEY/d' /root/.llama/distributions/sambanova/sambanova-run.yaml

# Expose your desired port
EXPOSE 8321

# Run the server
CMD ["bash", "-c", "/app/llama-stack/.venv/bin/llama stack run --image-type venv --image-name /app/llama-stack/.venv /root/.llama/distributions/sambanova/sambanova-run.yaml --port $LLAMA_STACK_PORT"]