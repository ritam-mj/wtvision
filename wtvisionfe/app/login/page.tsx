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

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg('');

    try {
      // POST user credentials to the Auth Microservice login endpoint
      // SimpleJWT defaults to '/token/' or '/auth/token/' depending on configuration.
      const response = await axiosAuth.post('/token/', {
        username: email, // simplejwt default authentication matches 'username' field (which can contain email)
        password,
      });

      const { access } = response.data;

      if (!access) {
        throw new Error('No access token received from authentication server.');
      }

      // Decode access token to read claims (user ID, email, role, etc.)
      const decoded = decodeJwt(access);
      
      // Update global context authentication state
      setAuth({
        user: {
          id: decoded?.user_id || '',
          email: decoded?.email || email,
          role: decoded?.role || 'user',
          username: decoded?.username || email.split('@')[0],
        },
        accessToken: access,
      });

      // Route the user to dashboard or home page
      router.push('/');
    } catch (err: any) {
      console.error('Login error:', err);
      if (err.response) {
        // Server responded with an error status (e.g. 401 Unauthorized)
        setErrorMsg(err.response.data?.detail || 'Invalid username or password.');
      } else if (err.request) {
        // Request made but no response received
        setErrorMsg('Auth Microservice is unreachable. Please verify it is running.');
      } else {
        setErrorMsg('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center bg-zinc-950 overflow-hidden font-sans">
      {/* Background Neon Glow Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-600/10 blur-[120px] pointer-events-none" />

      {/* Login Card Container */}
      <div className="w-full max-w-md px-6 z-10">
        <div className="w-full bg-zinc-900/60 backdrop-blur-xl border border-zinc-800/80 rounded-2xl p-8 shadow-2xl">
          
          {/* Brand/Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-violet-600/15 border border-violet-500/25 mb-4">
              <svg className="w-6 h-6 text-violet-400 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-white">Welcome back</h2>
            <p className="mt-2 text-sm text-zinc-400">Sign in to your wtvision backend</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            
            {/* Error Message */}
            {errorMsg && (
              <div className="p-3.5 rounded-lg bg-red-950/40 border border-red-800/50 text-red-300 text-xs flex items-start gap-2.5 animate-fadeIn">
                <svg className="w-4.5 h-4.5 text-red-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Email/Username Input */}
            <div className="space-y-2">
              <label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Username or Email
              </label>
              <div className="relative">
                <input
                  id="email"
                  type="text"
                  required
                  placeholder="admin@wtvision.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all duration-200"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Password
                </label>
                <a href="#" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">
                  Forgot password?
                </a>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-violet-500 focus:border-violet-500 transition-all duration-200"
                />
              </div>
            </div>

            {/* Remember Me & Terms */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="rounded border-zinc-800 bg-zinc-950 text-violet-600 focus:ring-0 focus:ring-offset-0 w-4 h-4 cursor-pointer"
                />
                <span className="text-xs text-zinc-400">Keep me signed in</span>
              </label>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full relative flex items-center justify-center bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-xl py-3 px-4 text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-violet-500 focus:ring-offset-zinc-950 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-violet-600/15 overflow-hidden"
            >
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Verifying credentials...</span>
                </div>
              ) : (
                <span>Sign In</span>
              )}
            </button>
          </form>

          {/* Footer details */}
          <div className="mt-8 pt-6 border-t border-zinc-800/80 text-center">
            <span className="text-xs text-zinc-500">
              Need access? Contact your wtvision administrator.
            </span>
          </div>

        </div>
      </div>
    </div>
  );
}
