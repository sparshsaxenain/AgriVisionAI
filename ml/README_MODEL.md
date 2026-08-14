# Connecting the supplied crop model

AgriVision isolates framework-specific behavior in `ml/model_adapter.py`. Every adapter returns the same `PredictionResult`, so the API, advisory engine, database, and Streamlit interface do not change when the model changes.

## Fastest supported path: TorchScript

1. Export the fine-tuned PyTorch model as a TorchScript file (`.pt` or `.pth`).
2. Copy it to `models/crop_model.pt`.
3. Put class labels in `ml/class_names.json` in the exact output-index order used during training.
4. In `.env`, set:

```dotenv
USE_MOCK_MODEL=false
MODEL_TYPE=pytorch
MODEL_PATH=./models/crop_model.pt
CLASS_NAMES_PATH=./ml/class_names.json
IMAGE_SIZE=224
```

5. Install CPU PyTorch using the command recommended for the target machine at https://pytorch.org/get-started/locally/ and restart AgriVision.

The PyTorch adapter first attempts `torch.jit.load`, then a serialized `nn.Module`. A raw `state_dict` cannot reveal its architecture. For a `state_dict`, add a project-specific adapter that constructs the known model architecture, loads the weights, and still returns `PredictionResult`.

## Keras / TensorFlow

Set `MODEL_TYPE=keras`, point `MODEL_PATH` to an `.h5`, `.keras`, or SavedModel artifact, install the compatible TensorFlow package, and keep the same ordered class-name file.

## Hugging Face directory

Create a small `HuggingFaceCropModelAdapter` beside the existing adapters. Load the image-classification model and processor from the directory, then normalize logits and labels into `PredictionResult`. No backend or frontend code needs to change.

## Preprocessing contract

The generic adapters resize to `IMAGE_SIZE` and scale pixels to `[0, 1]`. They intentionally do not guess the training mean, standard deviation, channel order, crop strategy, or label mapping. Match these to the supplied model before field use. If its preprocessing differs, override `preprocess()` in a project-specific adapter.

## Label and advisory mapping

- `ml/class_names.json`: exact model output-index order.
- `knowledge/crop_diseases.json`: advice keyed by model label.
- `AdvisoryService.normalize_label()`: aliases when the supplied label spelling differs.

An unknown class is handled safely with a generic expert-verification advisory instead of failing.

## Mock/real switching

- `USE_MOCK_MODEL=true`: deterministic demo predictions; no ML framework required.
- `USE_MOCK_MODEL=false`: real model is loaded when `MODEL_PATH` exists.
- If the path does not exist, the app deliberately falls back to mock mode so the hackathon demo remains runnable. The health endpoint reports `mock_mode`.

