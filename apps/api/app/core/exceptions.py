"""Custom exceptions for the Pixel2Layer pipeline."""


class Pixel2LayerError(Exception):
    """Base exception for all Pixel2Layer errors."""


class ImageProcessingError(Pixel2LayerError):
    """Error during image processing operations."""


class ImageDecodeError(ImageProcessingError):
    """Failed to decode image data."""


class ImageLoadError(ImageProcessingError):
    """Failed to load or process image file.
    
    Raised when image data is invalid or cannot be processed by the pipeline.
    """


class StorageError(Pixel2LayerError):
    """Error in storage operations."""


class InvalidStorageKeyError(StorageError):
    """Invalid storage key format."""


class StoreError(Pixel2LayerError):
    """Error in Store operations.
    
    Base exception for database and persistence layer errors.
    """


class StoreNotInitializedError(StoreError):
    """Store accessed before initialization."""


class UserExistsError(Pixel2LayerError):
    """User email already registered."""


class RegionDetectionError(ImageProcessingError):
    """Error during region detection."""


class PipelineError(Pixel2LayerError):
    """Error during pipeline execution.
    
    Raised when the reconstruction pipeline encounters an unrecoverable error
    during processing stages (segmentation, vectorization, etc.).
    """


class SegmentationError(PipelineError):
    """Error during image segmentation.
    
    Raised when the segmentation stage fails to detect foreground regions
    or encounters invalid image data.
    """


class ModelLoadError(Pixel2LayerError):
    """Failed to load ML model."""


class LoRAError(Pixel2LayerError):
    """Error in LoRA fine-tuning operations."""
