import requests
import os
import logging
import time
import gc
import psutil
from typing import Dict

from PIL import Image

from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import Sensor, SensorInfo
from ultralytics import YOLO

# Configure logging first
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        # logging.FileHandler('/app/logs/henhouse.log')  # File output
    ]
)

# MQTT Configuration - Get from environment variables
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() == "true"

# Configuration
DETECTION_INTERVAL = 900  # seconds between detections
IMAGE_SOURCE = os.getenv("IMAGE_SOURCE", "file")  # "file" or "url"
IMAGE_URL = os.getenv("IMAGE_URL", "not_set")
IMAGE_FILE = os.getenv("IMAGE_FILE", "snapshot.jpeg")


def setup_mqtt_sensors() -> Dict[str, Sensor]:
    """
    Set up MQTT sensors for Home Assistant discovery
    """
    # Configure MQTT settings
    mqtt_settings = Settings.MQTT(
        host=MQTT_HOST,
        port=MQTT_PORT,
        username=MQTT_USERNAME if MQTT_USERNAME else None,
        password=MQTT_PASSWORD if MQTT_PASSWORD else None,
        tls=MQTT_USE_TLS
    )
    
    # Define device information
    device_info = DeviceInfo(
        name="Henhouse Monitor",
        identifiers=["henhouse_001"],
        manufacturer="Custom",
        model="Egg Detector v1.0",
    )
    
    # Create sensor configurations
    egg_sensor_info = SensorInfo(
        name="Eggs",
        unique_id="henhouse_eggs",
        unit_of_measurement=None,
        icon="mdi:egg",
        device=device_info
    )
    
    chicken_sensor_info = SensorInfo(
        name="Chickens", 
        unique_id="henhouse_chickens",
        unit_of_measurement=None,
        icon="mdi:bird",
        device=device_info
    )
    
    # Create sensor settings
    egg_settings = Settings(mqtt=mqtt_settings, entity=egg_sensor_info)
    chicken_settings = Settings(mqtt=mqtt_settings, entity=chicken_sensor_info)
    
    # Instantiate sensors
    sensors = {
        "eggs": Sensor(egg_settings),
        "chickens": Sensor(chicken_settings)
    }
    
    logging.info("MQTT sensors initialized successfully")
    return sensors



def publish_counts_to_mqtt(sensors: Dict[str, Sensor], counts: Dict[str, int]):
    """
    Publish detection counts to MQTT sensors
    """
    try:
        sensors["eggs"].set_state(counts["egg"])
        sensors["chickens"].set_state(counts["chicken"])
        logging.info(f"Published to MQTT - Eggs: {counts['egg']}, Chickens: {counts['chicken']}")
    except Exception as e:
        logging.error(f"Failed to publish to MQTT: {e}")


def load_image() -> Image.Image:
    """
    Load image from either file or URL based on configuration
    """
    try:
        if IMAGE_SOURCE == "url":
            logging.debug(f"Loading image from URL: {IMAGE_URL}")
            response = requests.get(IMAGE_URL, stream=True, timeout=50)
            response.raise_for_status()
            image = Image.open(response.raw)
        else:
            logging.debug(f"Loading image from file: {IMAGE_FILE}")
            image = Image.open(IMAGE_FILE)
        
        logging.debug(f"Image loaded with size: {image.size}")
        return image
    except Exception as e:
        logging.error(f"Failed to load image: {e}")
        raise


def load_model() -> YOLO:
    """
    Load the YOLO model once at startup
    """
    try:
        logging.info("Loading YOLO model...")
        model = YOLO('models/henhouse.onnx', task="detect")
        logging.info("YOLO model loaded successfully")
        return model
    except Exception as e:
        logging.error(f"Failed to load YOLO model: {e}")
        raise


def perform_detection(model: YOLO, image: Image.Image, mqtt_sensors: Dict[str, Sensor] = None) -> Dict[str, int]:
    """
    Perform object detection on the given image and optionally publish to MQTT
    """
    
    try:
        logging.debug("Starting object detection...")
        result = model.predict(image, device="cpu")[0]
        counts = {name: 0 for name in result.names.values()}
    
        for box in result.boxes:
            class_id = int(box.cls)
            class_name = result.names[class_id]
            counts[class_name] += 1
        
        publish_counts_to_mqtt(mqtt_sensors, counts)
        
        # Explicit cleanup of result object
        del result
        return counts
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"Detection failed: {e}")
        # Return zero counts on error
        zero_counts = {"egg": 0, "chicken": 0}
        if mqtt_sensors:
            try:
                publish_counts_to_mqtt(mqtt_sensors, zero_counts)
            except Exception as mqtt_error:
                logging.error(f"Failed to publish zero counts after detection error: {mqtt_error}")
        return zero_counts


def get_memory_usage() -> float:
    """
    Get current memory usage in MB
    """
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # Convert bytes to MB


def main():
    logging.info("=== Starting Henhouse Monitor (Continuous Mode) ===")
    
    # Load YOLO model once at startup
    try:
        model = load_model()
        initial_memory = get_memory_usage()
        logging.info(f"Initial memory usage after model load: {initial_memory:.1f} MB")
    except Exception as e:
        logging.error(f"Failed to initialize YOLO model: {e}")
        return
    
    # Initialize MQTT sensors for Home Assistant
    mqtt_sensors = None
    try:
        mqtt_sensors = setup_mqtt_sensors()
        logging.info("MQTT integration enabled")
    except Exception as e:
        logging.warning(f"Failed to initialize MQTT sensors: {e}")
        logging.warning("Continuing without MQTT integration")
    
    logging.info(f"Starting continuous monitoring (detection every {DETECTION_INTERVAL} seconds)...")
    
    cycle_count = 0
    while True:
        try:
            cycle_count += 1
            current_memory = get_memory_usage()
            logging.debug(f"Starting detection cycle {cycle_count}, memory: {current_memory:.1f} MB")
            
            # Load fresh image
            image = load_image()
            
            # Perform detection and publish to MQTT
            perform_detection(model, image, mqtt_sensors)
            
            # Explicit cleanup
            del image
            
            # Force garbage collection every 10 cycles to help with memory management
            if cycle_count % 10 == 0:
                gc.collect()
                memory_after_gc = get_memory_usage()
                logging.info(f"Cycle {cycle_count}: Memory after GC: {memory_after_gc:.1f} MB")
            
        except KeyboardInterrupt:
            logging.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logging.error(f"Error in detection cycle: {e}")
            logging.info("Continuing with next cycle...")
        
        # Wait for next cycle
        logging.debug(f"Waiting {DETECTION_INTERVAL} seconds until next detection...")
        time.sleep(DETECTION_INTERVAL)
    
    logging.info("=== Henhouse Monitor shutdown completed ===")
    # Force flush all handlers
    for handler in logging.getLogger().handlers:
        handler.flush()


if __name__ == "__main__":
    main()
