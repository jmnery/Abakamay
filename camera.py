from flask import Response
import cv2
import numpy as np
import slr  # Import the new SLR module
from socketioInstance import socketio


def generate_frames():
    cap = cv2.VideoCapture(0)

    frame_count = 0
    frame_skip = 2  # Adjust the frame skip value as needed
    last_recognized_letter = None
    hand_present = False

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            break

        frame_count += 1
        if frame_count % frame_skip == 0:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Assume `slr.process_frame` may return just the recognized letter or None
            result = slr.process_frame(image_rgb)
            if isinstance(result, tuple):
                # If it’s a tuple, unpack it
                recognized_letter, hand_in_frame = result
            else:
                # If it’s not a tuple, assume it’s only the recognized letter
                recognized_letter = result
                # Assume hand is present if a letter is detected
                hand_in_frame = recognized_letter is not None

            if hand_in_frame:
                # Update the last recognized letter if a hand is detected in the frame
                hand_present = True
                last_recognized_letter = recognized_letter
                cv2.putText(image, f"Predicted Letter: {recognized_letter}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            else:
                # If hand is not detected and a letter was previously recognized
                if hand_present and last_recognized_letter:
                    # Emit the last recognized letter
                    socketio.emit('recognized_letter', {
                                  'letter': last_recognized_letter})
                    print("letter:", last_recognized_letter)
                    hand_present = False  # Reset hand presence tracking
                    last_recognized_letter = None  # Reset last recognized letter

        # Encode the frame
        ret, buffer = cv2.imencode('.jpg', image)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()
