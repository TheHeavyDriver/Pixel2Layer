"""SAM 2 fine-tuning pipeline for improved segmentation.

This module provides tools for fine-tuning SAM 2 with LoRA adapters:
- Dataset preparation from pipeline segmentation results
- LoRA-wrapped SAM 2 training
- Runtime segmentation with fine-tuned weights

See README.md for usage instructions.
"""

from app.services.finetune.sam2_segmenter import Sam2Segmenter

__all__ = ["Sam2Segmenter"]
