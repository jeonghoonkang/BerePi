
# Deep Learning 

## PyTorch

## Dark-net (YOLO)

### Object detection based on deep learning

#### Run on RPI3 B+


#### Run on Jetson Nano


## TensorFlow

- Under testing
  - [install TensorFlow on raspberry pi](https://www.tensorflow.org/install/install_raspbian)


## other similar, reference
- https://github.com/Guanghan/ROLO
- https://github.com/felixchenfy , https://github.com/felixchenfy/Realtime-Action-Recognition
- https://github.com/eldar/pose-tensorflow

## LLM model download

Use `model_downloader.py` to fetch and cache open-source models such as Gemma, Llama, or Qwen. Models are stored under `apps/deeplearning/models` and the function returns the path for reuse:

```
python model_downloader.py --model gemma
```

Other applications can import `download_model` from `model_downloader` to obtain the local path.
