import React, { createContext, useEffect, useState } from 'react';
import { hasSupabaseConfig, supabase, SUPABASE_CONFIG_MESSAGE } from '../services/supabase';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [screen, setScreen] = useState('login');

  useEffect(() => {
    if (!hasSupabaseConfig || !supabase) {
      setLoading(false);
      return undefined;
    }

    let mounted = true;

    supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!mounted) {
          return;
        }

        if (error) {
          setAuthError(error.message);
        }

        setSession(data.session ?? null);
        setLoading(false);
      })
      .catch((error) => {
        if (mounted) {
          setAuthError(error.message);
          setLoading(false);
        }
      });

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession ?? null);
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  async function signIn({ email, password }) {
    if (!supabase) {
      throw new Error(SUPABASE_CONFIG_MESSAGE);
    }

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    });

    if (error) {
      throw error;
    }

    setSession(data.session ?? null);
    setScreen('dashboard');
    return data;
  }

  async function signUp({ email, password, fullName, rut, phone, birthDate }) {
    if (!supabase) {
      throw new Error(SUPABASE_CONFIG_MESSAGE);
    }

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: import.meta.env.VITE_AUTH_REDIRECT_TO || window.location.origin,
        data: {
          full_name: fullName,
          rut,
          phone,
          birth_date: birthDate
        }
      }
    });

    if (error) {
      throw error;
    }

    return data;
  }

  async function signOut() {
    if (!supabase) {
      setSession(null);
      setScreen('login');
      return;
    }

    const { error } = await supabase.auth.signOut();

    if (error) {
      throw error;
    }

    setSession(null);
    setScreen('login');
  }

  const value = {
    accessToken: session?.access_token ?? '',
    authError,
    clearAuthError: () => setAuthError(''),
    hasSupabaseConfig,
    isAuthenticated: Boolean(session?.access_token),
    loading,
    screen,
    session,
    setScreen,
    signIn,
    signOut,
    signUp,
    user: session?.user ?? null
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
