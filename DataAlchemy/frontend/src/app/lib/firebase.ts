import { initializeApp } from "firebase/app";
import { browserLocalPersistence, getAuth, GoogleAuthProvider, setPersistence } from "firebase/auth";

export const FIREBASE_TOKEN_STORAGE_KEY = "dataalchemy.firebaseToken";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID ?? "",
};

export function isFirebaseConfigured() {
  return Object.values(firebaseConfig).every((value) => !!value);
}

export const firebaseApp = initializeApp(firebaseConfig);
export const firebaseAuth = getAuth(firebaseApp);
export const googleProvider = new GoogleAuthProvider();

void setPersistence(firebaseAuth, browserLocalPersistence);

export async function getCurrentIdToken() {
  const user = firebaseAuth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

export function getStoredIdToken() {
  return window.localStorage.getItem(FIREBASE_TOKEN_STORAGE_KEY);
}
