// Import the Firebase SDK from the CDN
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.0/firebase-app.js";
import {
  getFirestore,
  collection,
  getDoc,
  updateDoc,
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

// Function to get the learned letters and syllables
async function getLettersSyllablesForTags(userId, letter) {
  try {
    // Get the document reference for the user's data
    const userDocRef = doc(db, "users", userId);
    // Fetch the user's document data
    const userDocSnap = await getDoc(userDocRef);

    if (userDocSnap.exists()) {
      // Get the syllables map for the specified letter
      const userData = userDocSnap.data();
      const syllablesMap = userData.syllables || {}; // Default to empty object if no syllables data

      // Check if the letter exists in the user's syllables map
      if (syllablesMap[letter]) {
        const syllables = syllablesMap[letter]; // Get the map of syllables for the letter

        return { letter, syllables }; // Return the letter and its corresponding syllables map
      } else {
        console.log(`No syllables found for letter: ${letter}`);
        return null;
      }
    } else {
      console.log("User document not found!");
      return null;
    }
  } catch (error) {
    console.error("Error fetching syllables for letter:", error);
  }
}

// Function to add the learned letters and syllables
async function addSyllableToLearned(userId, letter, syllable) {
  try {
    const userDocRef = doc(db, "users", userId);

    // Get the current user's data
    const userDoc = await getDoc(userDocRef);

    if (!userDoc.exists()) {
      throw new Error(`User with ID ${userId} does not exist.`);
    }

    // Get the current syllables map or initialize it
    const syllables = userDoc.data().syllables || {};

    // Initialize the array for the letter if it doesn't exist
    if (!syllables[letter]) {
      syllables[letter] = [];
    }

    // Check if the syllable already exists
    if (!syllables[letter].includes(syllable)) {
      syllables[letter].push(syllable);

      // Update Firestore using updateDoc
      await updateDoc(userDocRef, { syllables });
      console.log(
        `Syllable '${syllable}' added under letter '${letter}' for user '${userId}'.`
      );
    } else {
      console.log(
        `Syllable '${syllable}' already exists under letter '${letter}' for user '${userId}'.`
      );
    }
  } catch (error) {
    console.error(`Error adding syllable: ${error.message}`);
    throw error;
  }
}

// Export the function for usage elsewhere
export {
  getLetterAndSyllables,
  getLettersSyllablesForTags,
  addSyllableToLearned,
};
