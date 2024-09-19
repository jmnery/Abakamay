from flask import Response
import cv2
import numpy as np
import slr  # Import the new SLR module


def generate_frames():
    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            break

        # Convert the image to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Process the image for hand detection and recognition
        recognized_letter = slr.process_frame(image_rgb)

        # Draw landmarks on the frame if hands are detected
        if recognized_letter:
            cv2.putText(image, f"Predicted Letter: {recognized_letter}", (
                10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

        # Encode the frame for streaming
        ret, buffer = cv2.imencode('.jpg', image)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()
