// c:\Users\ritam\wtvision\wtvisionfe\app\login\page.tsx
'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { axiosAuth } from '../api/axios';
import { useAuth } from '../context/AuthContext';

// Safe zero-dependency client-side JWT decoder
const decodeJwt = (token: string) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window
        .atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Failed to decode token:', error);
    return null;
  }
};

export default function LoginPage() {
  const { setAuth } = useAuth();
  const router = useRouter();

  const [isSignup, setIsSignup] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      if (isSignup) {
        // 1. Sign Up View: POST to the register endpoint
        await axiosAuth.post('/register/', {
          username,
          email,
          password,
        });

        setSuccessMsg('Account created successfully! Logging you in...');

        // 2. Automatic Login after successful Sign Up
        const loginResponse = await axiosAuth.post('/token/', {
          username, // Register username is used for token generation
          password,
        });

        const { access } = loginResponse.data;
        if (!access) {
          throw new Error('Access token missing post-signup auto-login.');
        }

        const decoded = decodeJwt(access);
        setAuth({
          user: {
            id: decoded?.user_id || '',
            email: decoded?.email || email,
            role: decoded?.role || 'user',
            username: decoded?.username || username,
          },
          accessToken: access,
        });

        // Delay slightly so the user sees the success message
        setTimeout(() => {
          router.push('/');
        }, 1000);

      } else {
        // Sign In View: POST user credentials to the Auth Microservice
        const response = await axiosAuth.post('/token/', {
          username: email, // SimpleJWT maps login to 'username'
          password,
        });

        const { access } = response.data;
        if (!access) {
          throw new Error('No access token received from authentication server.');
        }

        const decoded = decodeJwt(access);
        setAuth({
          user: {
            id: decoded?.user_id || '',
            email: decoded?.email || email,
            role: decoded?.role || 'user',
            username: decoded?.username || email.split('@')[0],
          },
          accessToken: access,
        });

        router.push('/');
      }
    } catch (err: any) {
      console.error('Authentication error:', err);
      if (err.response) {
        const errorData = err.response.data;
        // Parse Django serializer errors or standard detail errors
        if (typeof errorData === 'object' && !errorData.detail) {
          const firstKey = Object.keys(errorData)[0];
          const firstVal = errorData[firstKey];
          const msg = Array.isArray(firstVal) ? firstVal[0] : firstVal;
          setErrorMsg(`${firstKey}: ${msg}`);
        } else {
          setErrorMsg(errorData?.detail || 'Invalid username or password.');
        }
      } else if (err.request) {
        setErrorMsg('Auth Microservice is unreachable. Please verify it is running.');
      } else {
        setErrorMsg(err.message || 'An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Background Neon Glow Orbs */}
      <div className="glow-orb-1" />
      <div className="glow-orb-2" />
 
      {/* Login Card Container */}
      <div className="w-full max-w-md px-6 z-10">
        <div className="login-card">
          
          {/* Brand/Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-black/10 border border-black/20 mb-4">
              <svg className="w-6 h-6 text-black animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {isSignup ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                )}
              </svg>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-white">
              {isSignup ? 'Create an account' : 'Welcome back'}
            </h2>
            <p className="mt-2 text-sm text-zinc-400">
              {isSignup ? 'Sign up for a wtvision account' : 'Sign in to your wtvision backend'}
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            
            {/* Error Message */}
            {errorMsg && (
              <div className="p-3.5 rounded-lg bg-red-950/40 border border-red-800/50 text-red-300 text-xs flex items-start gap-2.5 animate-fadeIn">
                <svg className="w-4.5 h-4.5 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Success Message */}
            {successMsg && (
              <div className="p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 text-xs flex items-start gap-2.5 animate-fadeIn">
                <svg className="w-4.5 h-4.5 text-emerald-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{successMsg}</span>
              </div>
            )}

            {/* Username Input (Signup Only) */}
            {isSignup && (
              <div className="space-y-2">
                <label htmlFor="username" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  required
                  placeholder="johndoe"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-black focus:border-black transition-all duration-200"
                />
              </div>
            )}

            {/* Email/Username Input */}
            <div className="space-y-2">
              <label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                {isSignup ? 'Email Address' : 'Username or Email'}
              </label>
              <input
                id="email"
                type={isSignup ? 'email' : 'text'}
                required
                placeholder={isSignup ? 'john@example.com' : 'admin@wtvision.com'}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-black focus:border-black transition-all duration-200"
              />
            </div>

            {/* Password Input */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Password
                </label>
                {!isSignup && (
                  <a href="#" className="text-xs text-neutral-800 hover:text-black transition-colors font-medium">
                    Forgot password?
                  </a>
                )}
              </div>
              <input
                id="password"
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-black focus:border-black transition-all duration-200"
              />
            </div>

            {/* Keep Signed In Checkbox (Login Only) */}
            {!isSignup && (
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="rounded border-zinc-800 bg-zinc-950 text-black focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer"
                  />
                  <span className="text-xs text-zinc-400">Keep me signed in</span>
                </label>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full"
            >
              {isLoading ? (
                <div className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>{isSignup ? 'Registering...' : 'Verifying credentials...'}</span>
                </div>
              ) : (
                <span>{isSignup ? 'Sign Up' : 'Sign In'}</span>
              )}
            </button>
          </form>

          {/* Footer toggle */}
          <div className="mt-8 pt-6 border-t border-zinc-800/80 text-center">
            <button
              onClick={() => {
                setIsSignup(!isSignup);
                setErrorMsg('');
                setSuccessMsg('');
              }}
              className="text-xs text-neutral-800 hover:text-black font-semibold transition-colors"
            >
              {isSignup ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
