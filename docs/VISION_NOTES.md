# Vision tradeoffs: classical geometry vs pretrained detectors vs OCR fallbacks.

## Stage A — classical geometry (current default, `ClassicalDetector`)
- How: HSV red + dark segmentation inside the calibrated mat ROI, morphology,
  convex-contour area filter, `minAreaRect` heading, homography to cm.
- Pros: runs at full rate on a Pi 5 CPU at 640x480, fully explainable (every
  threshold is a named constant), no downloads, tuned in minutes on one frame.
- Cons: needs controlled conditions — fixed camera, plain matte mat, even
  diffuse light, saturated paper-car colors. Glare bands and dark desk edges
  are handled by the mat ROI mask, but a moved camera invalidates calibration
  (re-run `tools/calibrate_table.py`).
- Verdict: right default for a tabletop demo with paper cars.

## Stage B — pretrained detector (optional, not implemented)
- Idea: Ultralytics YOLO nano (ONNX/NCNN) for COCO `car`, selectable via
  `VEHICLE_DETECTOR=classical|yolo`, same `Detection` output contract.
- Pros: generalizes to varied lighting/backgrounds, no color assumptions.
- Cons: heavier on Pi CPU, and COCO `car` is trained on real cars — toy/paper
  cars detect poorly without fine-tuning (which the brief forbids: no training
  pipeline). Only switch if it measurably beats Stage A on recorded frames in
  `tests/data/`.
- Verdict: parked until Stage A demonstrably fails.

## Stage C — plate reading (Phase 6)
- Plan: crop plate region -> grayscale/upscale/adaptive-threshold ->
  Tesseract/EasyOCR -> normalize (A-Z, 0-9) -> fuzzy match `plates.json`
  (edit distance <= 1).
- Known weakness: OCR is the least reliable stage (handwritten plates, glare).
  Hence ordered fallbacks: (1) existing OpenRouter vision service on the crop,
  (2) roof ArUco ID -> plate registry lookup. Mitigations that actually work:
  bold sans print, high contrast, large plates, flat (uncurled) paper.

## Cross-cutting
- Vision at 5-10 FPS, 640x480 for analysis; full-res only for captures.
- Debounce (5-of-8) + hysteresis so one bad frame never tickets a car.
- Every stage degrades to a safe state (NullDetector, ticket-to-PNG, ERROR +
  motors stopped) when hardware or models are missing.
