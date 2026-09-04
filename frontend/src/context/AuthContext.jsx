import React, { createContext, useContext, useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

// Resolve Supabase configuration from Vite or standard environment
const supabaseUrl = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_SUPABASE_URL)
  || (typeof process !== 'undefined' && process.env?.VITE_SUPABASE_URL)
  || '';

const supabaseAnonKey = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_SUPABASE_ANON_KEY)
  || (typeof process !== 'undefined' && process.env?.VITE_SUPABASE_ANON_KEY)
  || '';

export const isSupabaseConfigured = Boolean(
  supabaseUrl &&
  supabaseAnonKey &&
  !supabaseUrl.includes('your-project')
);

// Instantiate authoritative client-side Supabase client
export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;

export const AuthContext = createContext(null);

/**
 * AuthProvider component that wraps the application and manages:
 * - Supabase user session state
 * - Authentication state (user, session, profile, loading, error)
 * - Sign-in, sign-up, sign-out actions
 * - Real-time onAuthStateChange synchronization
 */
export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Fetch verified user profile from backend database
  const fetchProfile = async (accessToken) => {
    try {
      const token = accessToken || session?.access_token;
      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const res = await fetch('/api/me', { headers });
      if (res.ok) {
        const data = await res.json();
        if (data?.user) {
          setProfile(data.user);
          return data.user;
        }
      }
    } catch (err) {
      console.warn('Could not fetch user profile from /api/me:', err);
    }
    return null;
  };

  useEffect(() => {
    let isMounted = true;

    if (!isSupabaseConfigured || !supabase) {
      setLoading(false);
      return;
    }

    // 1. Initial session resolution
    supabase.auth.getSession().then(async ({ data: { session: initialSession } }) => {
      if (!isMounted) return;
      setSession(initialSession);
      setUser(initialSession?.user ?? null);
      if (initialSession) {
        await fetchProfile(initialSession.access_token);
      }
      setLoading(false);
    }).catch(err => {
      console.error('Failed to resolve initial Supabase session:', err);
      if (isMounted) setLoading(false);
    });

    // 2. Real-time auth state subscription
    const { credentialsSubscription, data: authListener } = supabase.auth.onAuthStateChange(
      async (event, newSession) => {
        if (!isMounted) return;
        setSession(newSession);
        setUser(newSession?.user ?? null);
        if (newSession) {
          await fetchProfile(newSession.access_token);
        } else {
          setProfile(null);
        }
        setLoading(false);
      }
    );

    const subscription = authListener?.subscription || credentialsSubscription;

    return () => {
      isMounted = false;
      if (subscription?.unsubscribe) {
        subscription.unsubscribe();
      }
    };
  }, []);

  /**
   * Log in an existing user with email and password
   */
  const login = async (email, password) => {
    if (!isSupabaseConfigured || !supabase) {
      throw new Error('Supabase configuration unavailable. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.');
    }
    setAuthError(null);
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) {
      setAuthError(error.message);
      throw error;
    }
    if (data?.session) {
      setSession(data.session);
      setUser(data.session.user);
      await fetchProfile(data.session.access_token);
    }
    return data;
  };

  /**
   * Register a new user with metadata (fullName, role, referralCode)
   */
  const register = async ({ email, password, fullName, role = 'Client', referralCode = null }) => {
    if (!isSupabaseConfigured || !supabase) {
      throw new Error('Supabase configuration unavailable. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.');
    }
    setAuthError(null);
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          role,
          referral_code_used: referralCode,
        },
      },
    });
    if (error) {
      setAuthError(error.message);
      throw error;
    }
    if (data?.session) {
      setSession(data.session);
      setUser(data.session.user);
      await fetchProfile(data.session.access_token);
    }
    return data;
  };

  /**
   * Sign out current user
   */
  const logout = async () => {
    if (supabase) {
      try {
        await supabase.auth.signOut();
      } catch (err) {
        console.warn('Error signing out from Supabase:', err);
      }
    }
    setSession(null);
    setUser(null);
    setProfile(null);
    setAuthError(null);
  };

  /**
   * Explicitly refresh user profile and session state
   */
  const refreshProfile = async () => {
    return await fetchProfile();
  };

  const contextValue = {
    session,
    user,
    profile,
    loading,
    authError,
    isSupabaseConfigured,
    supabase,
    login,
    signIn: login,
    register,
    signUp: register,
    logout,
    signOut: logout,
    refreshProfile,
    isAuthenticated: Boolean(user),
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Custom React hook to access authentication context
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

/**
 * ProtectedRoute component for managing protected route access:
 * - Checks if user is authenticated
 * - Enforces role-based access controls (RBAC)
 * - Renders loading state while resolving authentication
 * - Renders custom fallback or unauthorized alert if access is denied
 */
export function ProtectedRoute({
  children,
  allowedRoles = [],
  fallback = null,
  loadingFallback = null,
}) {
  const { user, profile, loading } = useAuth();

  if (loading) {
    return loadingFallback || (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    );
  }

  // Not authenticated
  if (!user) {
    return fallback || (
      <div className="p-8 text-center bg-slate-900/60 border border-slate-800 rounded-xl max-w-md mx-auto my-12 shadow-xl">
        <h3 className="text-lg font-semibold text-slate-200">Authentication Required</h3>
        <p className="text-sm text-slate-400 mt-2">
          Please sign in to access this protected area of Intelliworks Industries.
        </p>
      </div>
    );
  }

  // Role validation check if roles are restricted
  const userRole = profile?.role || user.user_metadata?.role;
  if (allowedRoles.length > 0 && !allowedRoles.includes(userRole)) {
    return fallback || (
      <div className="p-8 text-center bg-rose-950/30 border border-rose-900/50 rounded-xl max-w-md mx-auto my-12 shadow-xl">
        <h3 className="text-lg font-semibold text-rose-300">Access Restricted</h3>
        <p className="text-sm text-slate-400 mt-2">
          Your account role ({userRole || 'Client'}) does not have permission to view this section.
        </p>
      </div>
    );
  }

  return children;
}

/**
 * RequireAuth alias for route protection
 */
export const RequireAuth = ProtectedRoute;

export default AuthContext;
