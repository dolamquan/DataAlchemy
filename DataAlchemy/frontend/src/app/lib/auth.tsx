import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createUserWithEmailAndPassword,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  type User,
} from "firebase/auth";
import { FIREBASE_TOKEN_STORAGE_KEY, firebaseAuth, googleProvider, isFirebaseConfigured } from "./firebase";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  configured: boolean;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOutUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const configured = isFirebaseConfigured();

  useEffect(() => {
    if (!configured) {
      setLoading(false);
      return;
    }
    const unsubscribe = onIdTokenChanged(firebaseAuth, async (nextUser) => {
      setUser(nextUser);
      if (nextUser) {
        const token = await nextUser.getIdToken();
        window.localStorage.setItem(FIREBASE_TOKEN_STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(FIREBASE_TOKEN_STORAGE_KEY);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, [configured]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      configured,
      async signInWithEmail(email: string, password: string) {
        await signInWithEmailAndPassword(firebaseAuth, email, password);
      },
      async signUpWithEmail(email: string, password: string) {
        await createUserWithEmailAndPassword(firebaseAuth, email, password);
      },
      async signInWithGoogle() {
        await signInWithPopup(firebaseAuth, googleProvider);
      },
      async signOutUser() {
        await signOut(firebaseAuth);
      },
    }),
    [configured, loading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
