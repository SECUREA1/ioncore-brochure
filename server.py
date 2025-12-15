<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>YOLOv8 TF.js Integration</title>
  <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0"></script>
</head>
<body>
  <h1>YOLOv8 Object Detection in Browser</h1>
  <input type="file" id="imageInput" accept="image/*">
  <canvas id="outputCanvas" width="640" height="640"></canvas>

  <script>
    async function loadAndDetect() {
      // Load the exported YOLOv8 TF.js model
      const model = await tf.loadGraphModel('./yolov8n_web_model/model.json');

      // Get image from input
      const input = document.getElementById('imageInput');
      input.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        const img = await createImageBitmap(file);
        const canvas = document.getElementById('outputCanvas');
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, 640, 640);

        // Preprocess image to tensor
        let tensor = tf.browser.fromPixels(canvas)
          .resizeNearestNeighbor([640, 640])  // Resize to model input size
          .toFloat()
          .div(tf.scalar(255.0))  // Normalize to [0,1]
          .expandDims();  // Add batch dimension

        // Run inference
        const predictions = await model.executeAsync(tensor);

        // Post-process predictions (parse boxes, classes, scores)
        // Note: YOLO output parsing - adapt based on model (e.g., boxes from predictions[0])
        console.log(predictions);  // Inspect and draw boxes (implement NMS, drawing logic here)

        // Example drawing (pseudo-code)
        // predictions.dataSync().forEach(pred => drawBox(ctx, pred));
      });
    }
    loadAndDetect();
  </script>
</body>
</html>
