import numpy as np
import tensorflow as tf
import mediapipe as mp

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False,
                       max_num_hands=1, min_detection_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# Load the Keras model
model_path = r"C:\Users\Daniel\Desktop\Flask Project\Abakada\abakada_flask\assets\newModel.h5"
model = tf.keras.models.load_model(model_path)

# List of letters for ASL gestures
letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def process_frame(image):
    # Process the image and detect hands
    result = hands.process(image)

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            # Extract hand landmarks
            hand_data = []
            for lm in hand_landmarks.landmark:
                hand_data.extend([lm.x, lm.y, lm.z])

            # Prepare data for model prediction
            hand_data = np.array(hand_data, dtype=np.float32)
            hand_data = np.expand_dims(
                hand_data, axis=0)  # Add batch dimension

            # Predict using the Keras model
            predictions = model.predict(hand_data)
            predicted_class = np.argmax(predictions)
            return letters[predicted_class]

    return None
