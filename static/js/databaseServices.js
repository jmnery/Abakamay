// Import the Firebase SDK from the CDN
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.0/firebase-app.js";
import {
  getFirestore,
  collection,
  getDoc,
  addDoc,
  doc,
} from "https://www.gstatic.com/firebasejs/11.0.0/firebase-firestore.js";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyBcZtR-dsbHDzcrjhGdIHzNh0ggFNvXPz0",
  authDomain: "abakada-flask.firebaseapp.com",
  databaseURL: "https://abakada-flask-default-rtdb.firebaseio.com",
  projectId: "abakada-flask",
  storageBucket: "abakada-flask.appspot.com",
  messagingSenderId: "456845640805",
  appId: "1:456845640805:web:1d85c1ac3826ce25d9728c",
};

// Initialize Firebase
initializeApp(firebaseConfig);
const db = getFirestore();

// Function to get letter and its corresponding syllables
async function getLetterAndSyllables(letter) {
  try {
    // Get the document reference for the specified letter
    const letterDocRef = doc(db, "words", letter);
    // Fetch the document data
    const letterDocSnap = await getDoc(letterDocRef);

    if (letterDocSnap.exists()) {
      // Get the syllables map from the document data
      const letterData = letterDocSnap.data();
      const syllables = letterData.syllables || {}; // Default to empty object if no syllables

      // Extract only the keys of the syllables object
      const syllableKeys = Object.keys(syllables);

      return { letter, syllables: syllableKeys }; // Return the letter and syllable keys
    } else {
      console.log("No such letter found!");
      return null;
    }
  } catch (error) {
    console.error("Error fetching letter and syllables:", error);
  }
}

// Function to get letter, syllables and words by letter
async function getAllByLetter(letter) {
  try {
    // Get the document reference for the specified letter
    const letterDocRef = doc(db, "words", letter);
    // Fetch the document data
    const letterDocSnap = await getDoc(letterDocRef);

    if (letterDocSnap.exists()) {
      // Get the syllables map from the document data
      const letterData = letterDocSnap.data();
      const syllables = letterData.syllables || {}; // Default to empty object if no syllables

      return { letter, syllables }; // Return the letter and corresponding syllables
    } else {
      console.log("No such letter found!");
      return null;
    }
  } catch (error) {
    console.error("Error fetching letter and syllables:", error);
  }
}

// Export the function for usage elsewhere
export { getLetterAndSyllables };
