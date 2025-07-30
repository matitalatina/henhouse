from ultralytics import YOLO
from ultralytics.data.split import autosplit

def train():

    # # Load a pretrained YOLO11n model
    model = YOLO("../models/yolo11s.pt")
    # model = YOLO("../models/henhouse.pt")

    # Train the model on the COCO8 dataset for 100 epochs
    train_results = model.train(
        data="dataset/data.yaml",  # Path to dataset configuration file
        epochs=100,  # Number of training epochs
        imgsz=640,  # Image size for training
        device="mps",  # Device to run on (e.g., 'cpu', 0, [0,1,2,3])
        pretrained=True,
        resume=False,
    )

    # Evaluate the model's performance on the validation set
    metrics = model.val()

    # Perform object detection on an image
    results = model("test.png")  # Predict on an image
    results[0].show()  # Display results
    model.export(format="onnx")
    # model = YOLO("../models/henhouse.pt")

def split_dataset():
    autosplit('dataset/project', (0.8, 0.2, 0.0), annotated_only=True)


if __name__ == "__main__":
    train()
    # split_dataset()
