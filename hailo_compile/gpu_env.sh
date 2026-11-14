# source me: DFC TensorFlow on the GPU. CUDA-12 runtime libs in ~/cuda12-libs (TF 2.18 needs 12.x; system CUDA is 13), cuDNN 9 reused from the user's existing install.
T=$HOME/cuda12-libs/nvidia
export LD_LIBRARY_PATH="$(ls -d $T/*/lib | tr '\n' ':')$HOME/.local/lib/python3.14/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH:-}"
export CUDA_VISIBLE_DEVICES=0   # DFC skips the GPU when the desktop already uses >5 % of its memory
