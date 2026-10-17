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

## Stage C — plate reading (Phase 6 / Implemented)
- Implementation: RapidOCR (ONNX Runtime CPU) runs directly on the perspective vehicle crop.
- Normalizes Indian vehicle plate numbers (`MH47AX5364`).
- Ambiguous or faint text is surfaced in the HUD Verification Gate modal for operator review/editing before citation printing.

## Stage D — Dynamic Line & Card Detection (`dynamic_detector.py` - Current Default)
- How: 
  1. Identifies drawn black marker divider lines on paper mat using adaptive thresholding and vertical line segment clustering.
  2. Synthesizes $N$ perspective parking bays dynamically without requiring fixed homography calibration.
  3. Detects multi-colored cards (yellow, red, black, blue, green) using a calibrated background paper mask ($S \le 65, V \ge 110$).
  4. Fits tight 4-point perspective quadrilaterals (`extract_tight_card_polygon`) using multi-scale convex hull approximation (`approxPolyDP`), resolving perspective foreshortening that artificially bloats orthogonal minimum area rectangles (`minAreaRect`).
  5. Uses per-contour convex hulls rather than global morphological closing to fill pen ink and license plate labels without bridging adjacent cards in neighboring bays.
  6. Evaluates relative violations: `STRADDLING` (line crossing) and `WRONG_ORIENTATION` (relative to bay axis).
- Pros: Requires zero calibration for new tabletop mats; adapts to any number of bays; tightly hugs card boundaries; zero cross-bay fusing.
- Performance: ~1 Hz in background monitor loop; lightweight OpenCV CPU operations on Raspberry Pi 5.

## Cross-cutting
- Vision at 5-10 FPS, 640x480 for analysis; full-res only for captures.
- Debounce (5-of-8) + hysteresis so one bad frame never tickets a car.
- Every stage degrades to a safe state (NullDetector, ticket-to-PNG, ERROR +
  motors stopped) when hardware or models are missing.

